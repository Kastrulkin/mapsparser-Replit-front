import type { Language } from '@/i18n/LanguageContext';

type GuidedTourStepText = {
  title: string;
  body: string;
};

export type GuidedTourCopy = {
  chapters: Record<'network-pulse' | 'card-content' | 'partnership', string> & Partial<Record<'automation', string>>;
  steps: Record<string, GuidedTourStepText>;
  entry: {
    pageTitle: string;
    openingTitle: string;
    preparing: string;
    unavailable: string;
    openFailed: string;
    retry: string;
    loading: string;
    robotAlt: string;
  };
  welcome: {
    eyebrow: string;
    headline: string;
    intro: string;
    capabilitiesTitle: string;
    capabilities: string[];
  };
  controls: {
    progressSaveError: string;
    launcherOpenAgain: string;
    launcherContinue: string;
    start: string;
    tourLabel: string;
    robotAlt: string;
    robotSuccessAlt: string;
    stepTemplate: string;
    pauseLabel: string;
    progressTemplate: string;
    targetMissing: string;
    openRoom: string;
    createAccount: string;
    finish: string;
    restart: string;
    highlight: string;
    previous: string;
    next: string;
    pause: string;
    skip: string;
  };
  banner: {
    notice: string;
    createAccount: string;
  };
};

const ru: GuidedTourCopy = {
  chapters: { 'network-pulse': 'Скрепка LocalOS', 'card-content': 'Карточка и контент', partnership: 'Партнёрство' },
  steps: {
    welcome: { title: 'Я помогу освоиться', body: 'За 8–10 минут мы посмотрим состояние сети, карточку на картах, контент и партнёрство. Вы можете свободно исследовать кабинет и в любой момент вернуться к маршруту.' },
    'operator-nav': { title: 'Оператор — управление через чат', body: 'Здесь можно управлять LocalOS обычными сообщениями. Например: создать пост, найти отзывы без ответа, изменить услугу или подготовить финансовый отчёт. Такой же интерфейс доступен в Telegram.' },
    'operator-overview': { title: 'Сводка по текущему бизнесу', body: 'Оператор знает состояние выбранного бизнеса и использует эти данные при выполнении ваших задач. Здесь отображаются показатели, которые требуют внимания прямо сейчас.' },
    'network-switcher': { title: 'Выбор бизнеса', body: 'Если у вас несколько филиалов, здесь можно быстро переключаться между ними. После выбора точки все данные, рекомендации и действия LocalOS будут относиться именно к этому бизнесу.' },
    'progress-nav': { title: 'Прогресс бизнеса', body: 'Здесь LocalOS собирает картину развития бизнеса: состояние карт и репутации, контента, партнёрств, автоматизации и допродаж. По каждому направлению видно, какие ступени уже пройдены, где есть проблема и какой следующий шаг даст практический результат.' },
    'progress-overview': { title: 'Подтверждённый путь', body: 'Цифры собираются из реальных данных разделов LocalOS: подключённых карт, готовых материалов, партнёров, запусков агентов и внедрённых допродаж. Здесь можно быстро понять, сколько ступеней уже пройдено и где требуется внимание.' },
    'progress-focus-action': { title: 'Сейчас важнее всего', body: 'LocalOS сравнивает проблемы и незавершённые задачи всех направлений и выбирает один приоритет. В блоке указаны причина, ожидаемый результат и кнопка, которая открывает нужное место для работы.' },
    'progress-areas': { title: 'Направления и ступени роста', body: 'Ниже представлены направления роста. Карты, контент, партнёрства, автоматизация и допродажи отслеживаются отдельно. Откройте строку: вы увидите подтверждённые ступени, текущую проблему, следующий результат и переход к действию.' },
    'progress-maps': { title: 'Карты и репутация', body: 'Данные приходят из последних сборов карточек, аудита, услуг и отзывов. Раскройте направление, чтобы увидеть пройденные ступени и показатели, а затем открыть полный аудит с конкретными рекомендациями.' },
    'progress-recent-results': { title: 'Недавние результаты', body: 'Здесь сохраняются подтверждённые события с датами: готовый аудит, контент-план, предложение партнёру, выполненная задача агента или внедрённая допродажа. Это история фактически сделанного, а не список советов.' },
    'card-nav': { title: 'Карточка на картах', body: 'В этом разделе собраны рейтинг, отзывы, услуги, фото и видимость на картах.' },
    'card-overview': { title: 'Работа с картами', body: 'Здесь собраны данные карточки из подключённых источников: рейтинг, отзывы, услуги, новости, поисковые запросы и конкуренты. Обновление данных в демо заблокировано.' },
    'card-services': { title: 'Услуги', body: 'В «Рогах и копытах» загружена 101 услуга. LocalOS находит дубли, слабые названия и незаполненные описания.' },
    'card-reviews': { title: 'Отзывы', body: 'Здесь собраны отзывы с карт. LocalOS показывает сообщения без ответа и помогает подготовить черновик, а публикация остаётся под вашим контролем.' },
    'card-news': { title: 'Новости', body: 'Здесь можно подготовить новость для карточки бизнеса, проверить текст и сохранить черновик. Публикация выполняется только после ручного подтверждения.' },
    'card-seo': { title: 'SEO-запросы', body: 'LocalOS собирает поисковые запросы и частотность, чтобы показать, по каким формулировкам клиенты ищут ваши услуги и какие темы стоит усилить.' },
    'card-competitors': { title: 'Конкуренты', body: 'Добавьте важные карточки рядом, чтобы сравнивать рейтинг, отзывы и действия конкурентов, а при необходимости запускать точечный аудит.' },
    'telegram-radar': { title: 'Telegram-радар', body: 'Радар собирает сигналы из выбранных Telegram-источников. Найденное сообщение можно открыть, сохранить как идею, подготовить ответ или скрыть.' },
    'average-ticket': { title: 'Допродажи', body: 'LocalOS использует статистику бизнеса, чтобы предложить пакеты, кросс-продажи и рабочие сценарии повышения среднего чека.' },
    'geo-promotion': { title: 'GEO-продвижение', body: 'Этот раздел помогает проверить видимость бизнеса в ответах AI-сервисов и определить, какие факты и материалы нужно усилить.' },
    'content-nav': { title: 'Контент проходит через проверку', body: 'Календарь хранит темы, черновики и статусы. Публикация всегда остаётся ручным решением.' },
    'content-calendar': { title: 'Подготовленный контент-план', body: 'Откройте ближайший материал и посмотрите, как идея превращается в черновик. Кнопки утверждения в демо не изменяют данные.' },
    'partnership-nav': { title: 'Партнёрства ведутся по этапам', body: 'Кандидаты, отбор, письма, отправка и ответы не смешиваются в один список.' },
    'partnership-workspace': { title: 'От кандидата до диалога', body: 'Для демо уже подготовлены партнёры и история кампании. Все исходящие действия заблокированы.' },
    'partnership-candidates': { title: 'История с «Ромашкой»', body: 'Карточка партнёра хранит контекст, предложение, канал связи и следующее действие.' },
    finish: { title: 'Маршрут пройден', body: 'Теперь можно открыть цифровую комнату «Ромашки» и посмотреть на предложение глазами лида. Или создайте свой аккаунт и загрузите реальный бизнес.' },
  },
  entry: { pageTitle: 'Интерактивное демо LocalOS', openingTitle: 'Открываем «Рога и копыта»', preparing: 'Готовим личную демо-сессию. Данные аккаунта не изменятся.', unavailable: 'Демо сейчас недоступно', openFailed: 'Не удалось открыть демо', retry: 'Повторить', loading: 'Загружаем витрину', robotAlt: 'Робот LocalOS' },
  welcome: {
    eyebrow: 'Интерактивное демо LocalOS',
    headline: 'Получайте больше клиентов из карт, отзывов и соцсетей — без ручной рутины',
    intro: 'LocalOS помогает владельцу малого бизнеса вести Яндекс Карты, 2ГИС и Google, отвечать на отзывы, готовить посты и новости, смотреть конкурентов рядом и понимать, что влияет на заявки, выручку и средний чек.',
    capabilitiesTitle: 'Что можно сделать в LocalOS',
    capabilities: ['Понять, что исправить в карточке бизнеса', 'Улучшить услуги, описания, фото и новости для карт', 'Отвечать на отзывы и повышать рейтинг', 'Готовить посты для соцсетей без вопроса «что выкладывать?»', 'Смотреть, что делают конкуренты рядом', 'Находить партнёров со схожей аудиторией', 'Поручать повторяющиеся задачи обычным языком'],
  },
  controls: { progressSaveError: 'Не удалось сохранить прогресс. Попробуйте ещё раз.', launcherOpenAgain: 'Открыть обучение снова', launcherContinue: 'Продолжить обучение', start: 'Начать знакомство', tourLabel: 'Интерактивное обучение LocalOS', robotAlt: 'Робот LocalOS', robotSuccessAlt: 'Робот LocalOS завершил обучение', stepTemplate: 'Шаг {current} из {total}', pauseLabel: 'Поставить обучение на паузу', progressTemplate: 'Прогресс {percent}%', targetMissing: 'Элемент ещё не загрузился. Можно показать его повторно или перейти дальше.', openRoom: 'Открыть комнату', createAccount: 'Создать аккаунт', finish: 'Завершить маршрут', restart: 'Начать заново', highlight: 'Подсветить на странице', previous: 'Предыдущий шаг', next: 'Дальше', pause: 'Пауза', skip: 'Пропустить обучение' },
  banner: { notice: 'Демо-режим · данные не изменяются', createAccount: 'Создать свой аккаунт' },
};

const en: GuidedTourCopy = {
  chapters: { 'network-pulse': 'LocalOS guide', 'card-content': 'Listing and content', partnership: 'Partnerships' },
  steps: {
    welcome: { title: 'I’ll show you around', body: 'In 8–10 minutes, we’ll review your network, map listing, content, and partnerships. Feel free to explore the dashboard and return to the tour at any time.' },
    'operator-nav': { title: 'Operator — control through chat', body: 'Manage LocalOS with ordinary messages: create a post, find unanswered reviews, update a service, or prepare a financial report. The same interface is available in Telegram.' },
    'operator-overview': { title: 'Current business overview', body: 'Operator knows the state of the selected business and uses it when handling your tasks. This area shows the metrics that need attention right now.' },
    'network-switcher': { title: 'Choose a business', body: 'If you have several locations, switch between them here. After you choose one, all LocalOS data, recommendations, and actions apply to that business.' },
    'progress-nav': { title: 'Business progress', body: 'LocalOS brings together growth across maps and reputation, content, partnerships, automation, and upsells. Each area shows completed stages, the current issue, and the next step that will deliver a practical result.' },
    'progress-overview': { title: 'Verified progress', body: 'The numbers come from real LocalOS data: connected listings, prepared materials, partners, agent runs, and implemented upsells. See at a glance how many stages are complete and where attention is needed.' },
    'progress-focus-action': { title: 'What matters most now', body: 'LocalOS compares issues and unfinished tasks across all areas and selects one priority. The card explains why, the expected result, and opens the right place to work.' },
    'progress-areas': { title: 'Growth areas and stages', body: 'The growth areas are listed below. Maps, content, partnerships, automation, and upsells are tracked separately. Open a row to see verified stages, the current issue, the next result, and the action to take.' },
    'progress-maps': { title: 'Maps and reputation', body: 'Data comes from recent listing scans, audits, services, and reviews. Expand the area to see completed stages and metrics, then open the full audit for specific recommendations.' },
    'progress-recent-results': { title: 'Recent results', body: 'Verified, dated events appear here: a completed audit, content plan, partner offer, finished agent task, or implemented upsell. This is a history of work actually done, not a list of suggestions.' },
    'card-nav': { title: 'Map listing', body: 'This section brings together ratings, reviews, services, photos, and map visibility.' },
    'card-overview': { title: 'Working with maps', body: 'See listing data from connected sources: rating, reviews, services, news, search queries, and competitors. Data refresh is disabled in the demo.' },
    'card-services': { title: 'Services', body: '“Roga i Kopyta” has 101 services loaded. LocalOS finds duplicates, weak names, and missing descriptions.' },
    'card-reviews': { title: 'Reviews', body: 'Reviews from map platforms appear here. LocalOS highlights unanswered messages and helps prepare a draft while publication stays under your control.' },
    'card-news': { title: 'News', body: 'Prepare a news item for the business listing, review the text, and save a draft. Publishing happens only after manual approval.' },
    'card-seo': { title: 'SEO queries', body: 'LocalOS collects search queries and frequency data to show how customers search for your services and which topics deserve more attention.' },
    'card-competitors': { title: 'Competitors', body: 'Add important nearby listings to compare ratings, reviews, and competitor activity, then run a focused audit when needed.' },
    'telegram-radar': { title: 'Telegram Radar', body: 'The radar collects signals from selected Telegram sources. Open a found message, save it as an idea, prepare a reply, or hide it.' },
    'average-ticket': { title: 'Upsells', body: 'LocalOS uses business statistics to suggest packages, cross-sells, and practical ways to increase the average ticket.' },
    'geo-promotion': { title: 'GEO promotion', body: 'Check how visible the business is in AI-service answers and identify which facts and materials should be strengthened.' },
    'content-nav': { title: 'Content goes through review', body: 'The calendar stores topics, drafts, and statuses. Publishing always remains a manual decision.' },
    'content-calendar': { title: 'Prepared content plan', body: 'Open the next item and see how an idea becomes a draft. Approval buttons do not change data in the demo.' },
    'partnership-nav': { title: 'Partnerships move in stages', body: 'Candidates, selection, messages, sending, and replies are kept in separate stages.' },
    'partnership-workspace': { title: 'From candidate to conversation', body: 'Partners and campaign history are already prepared for the demo. All outbound actions are disabled.' },
    'partnership-candidates': { title: 'The “Romashka” story', body: 'The partner card keeps the context, offer, contact channel, and next action together.' },
    finish: { title: 'Tour complete', body: 'You can now open Romashka’s digital room and view the offer as a lead would. Or create your own account and add a real business.' },
  },
  entry: { pageTitle: 'LocalOS interactive demo', openingTitle: 'Opening “Roga i Kopyta”', preparing: 'Preparing your personal demo session. Account data will not be changed.', unavailable: 'The demo is currently unavailable', openFailed: 'Could not open the demo', retry: 'Try again', loading: 'Loading the showcase', robotAlt: 'LocalOS robot' },
  welcome: { eyebrow: 'LocalOS interactive demo', headline: 'Get more customers from maps, reviews, and social media — without repetitive manual work', intro: 'LocalOS helps small-business owners manage Yandex Maps, 2GIS, and Google, reply to reviews, prepare posts and news, monitor nearby competitors, and understand what affects leads, revenue, and average ticket.', capabilitiesTitle: 'What you can do in LocalOS', capabilities: ['See what to fix in your business listing', 'Improve services, descriptions, photos, and listing news', 'Reply to reviews and improve your rating', 'Prepare social posts without wondering what to publish', 'See what nearby competitors are doing', 'Find partners with a similar audience', 'Delegate recurring tasks in ordinary language'] },
  controls: { progressSaveError: 'Could not save your progress. Please try again.', launcherOpenAgain: 'Open the tour again', launcherContinue: 'Continue the tour', start: 'Start the tour', tourLabel: 'LocalOS interactive tour', robotAlt: 'LocalOS robot', robotSuccessAlt: 'LocalOS robot completed the tour', stepTemplate: 'Step {current} of {total}', pauseLabel: 'Pause the tour', progressTemplate: 'Progress {percent}%', targetMissing: 'This element has not loaded yet. Highlight it again or continue to the next step.', openRoom: 'Open the room', createAccount: 'Create account', finish: 'Finish the tour', restart: 'Start again', highlight: 'Highlight on page', previous: 'Previous step', next: 'Next', pause: 'Pause', skip: 'Skip the tour' },
  banner: { notice: 'Demo mode · data cannot be changed', createAccount: 'Create your account' },
};

const fr: GuidedTourCopy = {
  chapters: { 'network-pulse': 'Guide LocalOS', 'card-content': 'Fiche et contenu', partnership: 'Partenariats' },
  steps: {
    welcome: { title: 'Je vous guide', body: 'En 8 à 10 minutes, nous verrons le réseau, la fiche sur les cartes, le contenu et les partenariats. Vous pouvez explorer librement le tableau de bord et reprendre la visite à tout moment.' },
    'operator-nav': { title: 'Opérateur — piloter par le chat', body: 'Pilotez LocalOS avec des messages simples : créez une publication, trouvez les avis sans réponse, modifiez un service ou préparez un rapport financier. La même interface est disponible dans Telegram.' },
    'operator-overview': { title: 'Vue d’ensemble de l’entreprise', body: 'L’Opérateur connaît l’état de l’entreprise sélectionnée et utilise ces données pour vos tâches. Cette zone affiche les indicateurs qui demandent votre attention maintenant.' },
    'network-switcher': { title: 'Choisir une entreprise', body: 'Si vous avez plusieurs établissements, passez rapidement de l’un à l’autre ici. Toutes les données, recommandations et actions LocalOS concerneront alors l’établissement choisi.' },
    'progress-nav': { title: 'Progression de l’entreprise', body: 'LocalOS réunit la progression des cartes et de la réputation, du contenu, des partenariats, de l’automatisation et des ventes additionnelles. Chaque axe montre les étapes validées, le problème actuel et la prochaine action utile.' },
    'progress-overview': { title: 'Progression confirmée', body: 'Les chiffres viennent de données réelles de LocalOS : fiches connectées, contenus prêts, partenaires, lancements d’agents et ventes additionnelles mises en place. Voyez rapidement les étapes terminées et les points d’attention.' },
    'progress-focus-action': { title: 'La priorité du moment', body: 'LocalOS compare les problèmes et tâches inachevées de tous les axes et choisit une priorité. Le bloc explique la raison, le résultat attendu et ouvre le bon espace de travail.' },
    'progress-areas': { title: 'Axes et étapes de croissance', body: 'Les axes de croissance sont présentés ci-dessous. Cartes, contenu, partenariats, automatisation et ventes additionnelles sont suivis séparément. Ouvrez une ligne pour voir les étapes validées, le problème actuel, le prochain résultat et l’action à lancer.' },
    'progress-maps': { title: 'Cartes et réputation', body: 'Les données viennent des derniers relevés de fiches, audits, services et avis. Dépliez l’axe pour voir les étapes et indicateurs, puis ouvrez l’audit complet pour des recommandations précises.' },
    'progress-recent-results': { title: 'Résultats récents', body: 'Les événements confirmés et datés sont conservés ici : audit terminé, plan de contenu, proposition partenaire, tâche d’agent réalisée ou vente additionnelle déployée. C’est l’historique du travail réellement accompli.' },
    'card-nav': { title: 'Fiche sur les cartes', body: 'Cette section rassemble la note, les avis, les services, les photos et la visibilité sur les cartes.' },
    'card-overview': { title: 'Travailler avec les cartes', body: 'Retrouvez les données des sources connectées : note, avis, services, actualités, requêtes de recherche et concurrents. L’actualisation est désactivée dans la démo.' },
    'card-services': { title: 'Services', body: '« Roga i Kopyta » contient 101 services. LocalOS détecte les doublons, les intitulés faibles et les descriptions manquantes.' },
    'card-reviews': { title: 'Avis', body: 'Les avis des plateformes cartographiques sont réunis ici. LocalOS signale ceux sans réponse et aide à préparer un brouillon ; la publication reste sous votre contrôle.' },
    'card-news': { title: 'Actualités', body: 'Préparez une actualité pour la fiche, vérifiez le texte et enregistrez un brouillon. La publication n’a lieu qu’après confirmation manuelle.' },
    'card-seo': { title: 'Requêtes SEO', body: 'LocalOS collecte les requêtes et leur fréquence pour montrer comment les clients cherchent vos services et quels sujets renforcer.' },
    'card-competitors': { title: 'Concurrents', body: 'Ajoutez les fiches importantes à proximité pour comparer notes, avis et actions des concurrents, puis lancez un audit ciblé si nécessaire.' },
    'telegram-radar': { title: 'Radar Telegram', body: 'Le radar collecte les signaux de sources Telegram choisies. Ouvrez un message trouvé, gardez-le comme idée, préparez une réponse ou masquez-le.' },
    'average-ticket': { title: 'Ventes additionnelles', body: 'LocalOS utilise les statistiques de l’entreprise pour proposer des offres groupées, des ventes croisées et des scénarios concrets afin d’augmenter le panier moyen.' },
    'geo-promotion': { title: 'Promotion GEO', body: 'Vérifiez la visibilité de l’entreprise dans les réponses des services d’IA et identifiez les faits et contenus à renforcer.' },
    'content-nav': { title: 'Le contenu passe par une validation', body: 'Le calendrier conserve les sujets, brouillons et statuts. La publication reste toujours une décision manuelle.' },
    'content-calendar': { title: 'Plan de contenu préparé', body: 'Ouvrez le prochain contenu et voyez comment une idée devient un brouillon. Les boutons de validation ne modifient aucune donnée dans la démo.' },
    'partnership-nav': { title: 'Des partenariats par étapes', body: 'Candidats, sélection, messages, envoi et réponses restent organisés en étapes distinctes.' },
    'partnership-workspace': { title: 'Du candidat à la conversation', body: 'Des partenaires et un historique de campagne sont déjà préparés pour la démo. Toutes les actions sortantes sont désactivées.' },
    'partnership-candidates': { title: 'L’histoire avec « Romashka »', body: 'La fiche partenaire conserve le contexte, la proposition, le canal de contact et la prochaine action.' },
    finish: { title: 'Visite terminée', body: 'Vous pouvez maintenant ouvrir l’espace numérique de Romashka et voir la proposition comme un prospect. Ou créez votre compte et ajoutez une entreprise réelle.' },
  },
  entry: { pageTitle: 'Démo interactive LocalOS', openingTitle: 'Ouverture de « Roga i Kopyta »', preparing: 'Préparation de votre session de démo personnelle. Les données du compte ne seront pas modifiées.', unavailable: 'La démo est momentanément indisponible', openFailed: 'Impossible d’ouvrir la démo', retry: 'Réessayer', loading: 'Chargement de la vitrine', robotAlt: 'Robot LocalOS' },
  welcome: { eyebrow: 'Démo interactive LocalOS', headline: 'Attirez plus de clients grâce aux cartes, aux avis et aux réseaux sociaux — sans tâches manuelles répétitives', intro: 'LocalOS aide les petites entreprises à gérer Yandex Maps, 2GIS et Google, répondre aux avis, préparer des publications et actualités, suivre les concurrents proches et comprendre ce qui influence les demandes, le chiffre d’affaires et le panier moyen.', capabilitiesTitle: 'Ce que vous pouvez faire dans LocalOS', capabilities: ['Voir quoi corriger dans la fiche de l’entreprise', 'Améliorer services, descriptions, photos et actualités', 'Répondre aux avis et améliorer la note', 'Préparer des publications sociales sans chercher quoi publier', 'Suivre les actions des concurrents proches', 'Trouver des partenaires avec une audience similaire', 'Confier les tâches répétitives en langage courant'] },
  controls: { progressSaveError: 'Impossible d’enregistrer votre progression. Réessayez.', launcherOpenAgain: 'Revoir la visite', launcherContinue: 'Continuer la visite', start: 'Commencer la visite', tourLabel: 'Visite interactive LocalOS', robotAlt: 'Robot LocalOS', robotSuccessAlt: 'Le robot LocalOS a terminé la visite', stepTemplate: 'Étape {current} sur {total}', pauseLabel: 'Mettre la visite en pause', progressTemplate: 'Progression {percent} %', targetMissing: 'Cet élément n’est pas encore chargé. Vous pouvez le remettre en évidence ou continuer.', openRoom: 'Ouvrir l’espace', createAccount: 'Créer un compte', finish: 'Terminer la visite', restart: 'Recommencer', highlight: 'Mettre en évidence', previous: 'Étape précédente', next: 'Suivant', pause: 'Pause', skip: 'Ignorer la visite' },
  banner: { notice: 'Mode démo · les données ne sont pas modifiées', createAccount: 'Créer votre compte' },
};

const es: GuidedTourCopy = {
  chapters: { 'network-pulse': 'Guía de LocalOS', 'card-content': 'Ficha y contenido', partnership: 'Colaboraciones' },
  steps: {
    welcome: { title: 'Te ayudaré a orientarte', body: 'En 8–10 minutos revisaremos la red, la ficha en mapas, el contenido y las colaboraciones. Puedes explorar el panel libremente y volver al recorrido cuando quieras.' },
    'operator-nav': { title: 'Operador: controla mediante chat', body: 'Gestiona LocalOS con mensajes normales: crea una publicación, busca reseñas sin respuesta, cambia un servicio o prepara un informe financiero. La misma interfaz está disponible en Telegram.' },
    'operator-overview': { title: 'Resumen del negocio actual', body: 'El Operador conoce el estado del negocio seleccionado y usa esos datos al realizar tus tareas. Aquí aparecen los indicadores que necesitan atención ahora.' },
    'network-switcher': { title: 'Selecciona un negocio', body: 'Si tienes varias ubicaciones, cambia rápidamente entre ellas aquí. Todos los datos, recomendaciones y acciones de LocalOS se aplicarán al negocio elegido.' },
    'progress-nav': { title: 'Progreso del negocio', body: 'LocalOS reúne el avance en mapas y reputación, contenido, colaboraciones, automatización y ventas adicionales. Cada área muestra las etapas completadas, el problema actual y el siguiente paso con resultado práctico.' },
    'progress-overview': { title: 'Progreso confirmado', body: 'Las cifras proceden de datos reales de LocalOS: fichas conectadas, materiales preparados, colaboradores, ejecuciones de agentes y ventas adicionales implantadas. Comprueba qué etapas están completas y dónde hace falta atención.' },
    'progress-focus-action': { title: 'Lo más importante ahora', body: 'LocalOS compara los problemas y tareas pendientes de todas las áreas y elige una prioridad. El bloque explica el motivo, el resultado esperado y abre el lugar correcto para trabajar.' },
    'progress-areas': { title: 'Áreas y etapas de crecimiento', body: 'A continuación se muestran las áreas de crecimiento. Mapas, contenido, colaboraciones, automatización y ventas adicionales se controlan por separado. Abre una fila para ver etapas confirmadas, el problema actual, el siguiente resultado y la acción.' },
    'progress-maps': { title: 'Mapas y reputación', body: 'Los datos proceden de las últimas recopilaciones de fichas, auditorías, servicios y reseñas. Despliega el área para ver etapas e indicadores y abre la auditoría completa para obtener recomendaciones concretas.' },
    'progress-recent-results': { title: 'Resultados recientes', body: 'Aquí se guardan eventos confirmados con fecha: una auditoría lista, un plan de contenido, una propuesta a un colaborador, una tarea de agente completada o una venta adicional implantada. Es un historial de trabajo real, no una lista de consejos.' },
    'card-nav': { title: 'Ficha en mapas', body: 'Esta sección reúne valoración, reseñas, servicios, fotos y visibilidad en mapas.' },
    'card-overview': { title: 'Trabajo con mapas', body: 'Consulta los datos de la ficha desde fuentes conectadas: valoración, reseñas, servicios, noticias, búsquedas y competidores. La actualización está bloqueada en la demo.' },
    'card-services': { title: 'Servicios', body: '“Roga i Kopyta” tiene 101 servicios cargados. LocalOS encuentra duplicados, nombres poco claros y descripciones incompletas.' },
    'card-reviews': { title: 'Reseñas', body: 'Aquí se reúnen las reseñas de los mapas. LocalOS destaca las que no tienen respuesta y ayuda a preparar un borrador; la publicación sigue bajo tu control.' },
    'card-news': { title: 'Noticias', body: 'Prepara una noticia para la ficha, revisa el texto y guarda un borrador. Solo se publica después de una confirmación manual.' },
    'card-seo': { title: 'Consultas SEO', body: 'LocalOS recopila búsquedas y frecuencia para mostrar cómo buscan tus servicios los clientes y qué temas conviene reforzar.' },
    'card-competitors': { title: 'Competidores', body: 'Añade fichas cercanas importantes para comparar valoraciones, reseñas y acciones de la competencia, y ejecuta una auditoría específica cuando sea necesario.' },
    'telegram-radar': { title: 'Radar de Telegram', body: 'El radar recopila señales de las fuentes de Telegram seleccionadas. Abre un mensaje encontrado, guárdalo como idea, prepara una respuesta u ocúltalo.' },
    'average-ticket': { title: 'Ventas adicionales', body: 'LocalOS usa las estadísticas del negocio para proponer paquetes, ventas cruzadas y escenarios prácticos que aumenten el ticket medio.' },
    'geo-promotion': { title: 'Promoción GEO', body: 'Comprueba la visibilidad del negocio en las respuestas de servicios de IA y determina qué datos y materiales hay que reforzar.' },
    'content-nav': { title: 'El contenido pasa por revisión', body: 'El calendario guarda temas, borradores y estados. Publicar siempre sigue siendo una decisión manual.' },
    'content-calendar': { title: 'Plan de contenido preparado', body: 'Abre el siguiente material y observa cómo una idea se convierte en borrador. Los botones de aprobación no cambian datos en la demo.' },
    'partnership-nav': { title: 'Colaboraciones por etapas', body: 'Candidatos, selección, mensajes, envío y respuestas se mantienen en etapas separadas.' },
    'partnership-workspace': { title: 'Del candidato a la conversación', body: 'La demo ya incluye colaboradores y un historial de campaña. Todas las acciones salientes están bloqueadas.' },
    'partnership-candidates': { title: 'La historia con “Romashka”', body: 'La ficha del colaborador reúne el contexto, la propuesta, el canal de contacto y la siguiente acción.' },
    finish: { title: 'Recorrido completado', body: 'Ahora puedes abrir la sala digital de Romashka y ver la propuesta como la vería un posible cliente. O crea tu cuenta y añade un negocio real.' },
  },
  entry: { pageTitle: 'Demo interactiva de LocalOS', openingTitle: 'Abriendo “Roga i Kopyta”', preparing: 'Estamos preparando tu sesión de demo personal. Los datos de la cuenta no cambiarán.', unavailable: 'La demo no está disponible ahora', openFailed: 'No se pudo abrir la demo', retry: 'Reintentar', loading: 'Cargando la muestra', robotAlt: 'Robot de LocalOS' },
  welcome: { eyebrow: 'Demo interactiva de LocalOS', headline: 'Consigue más clientes desde mapas, reseñas y redes sociales, sin tareas manuales repetitivas', intro: 'LocalOS ayuda a pequeños negocios a gestionar Yandex Maps, 2GIS y Google, responder reseñas, preparar publicaciones y noticias, observar competidores cercanos y entender qué influye en las solicitudes, los ingresos y el ticket medio.', capabilitiesTitle: 'Qué puedes hacer en LocalOS', capabilities: ['Saber qué corregir en la ficha del negocio', 'Mejorar servicios, descripciones, fotos y noticias', 'Responder reseñas y mejorar la valoración', 'Preparar publicaciones sin preguntarte qué publicar', 'Ver qué hacen los competidores cercanos', 'Encontrar colaboradores con un público similar', 'Delegar tareas repetitivas con lenguaje normal'] },
  controls: { progressSaveError: 'No se pudo guardar el progreso. Inténtalo de nuevo.', launcherOpenAgain: 'Abrir el recorrido de nuevo', launcherContinue: 'Continuar el recorrido', start: 'Empezar el recorrido', tourLabel: 'Recorrido interactivo de LocalOS', robotAlt: 'Robot de LocalOS', robotSuccessAlt: 'El robot de LocalOS completó el recorrido', stepTemplate: 'Paso {current} de {total}', pauseLabel: 'Pausar el recorrido', progressTemplate: 'Progreso {percent} %', targetMissing: 'Este elemento todavía no se ha cargado. Puedes resaltarlo de nuevo o continuar.', openRoom: 'Abrir la sala', createAccount: 'Crear cuenta', finish: 'Finalizar recorrido', restart: 'Empezar de nuevo', highlight: 'Resaltar en la página', previous: 'Paso anterior', next: 'Siguiente', pause: 'Pausa', skip: 'Omitir el recorrido' },
  banner: { notice: 'Modo demo · los datos no se modifican', createAccount: 'Crear tu cuenta' },
};

const el: GuidedTourCopy = {
  chapters: { 'network-pulse': 'Οδηγός LocalOS', 'card-content': 'Καταχώριση και περιεχόμενο', partnership: 'Συνεργασίες' },
  steps: {
    welcome: { title: 'Θα σας ξεναγήσω', body: 'Σε 8–10 λεπτά θα δούμε το δίκτυο, την καταχώριση στους χάρτες, το περιεχόμενο και τις συνεργασίες. Μπορείτε να εξερευνήσετε ελεύθερα τον πίνακα και να επιστρέψετε στην ξενάγηση οποτεδήποτε.' },
    'operator-nav': { title: 'Operator — διαχείριση μέσω συνομιλίας', body: 'Διαχειριστείτε το LocalOS με απλά μηνύματα: δημιουργήστε ανάρτηση, βρείτε κριτικές χωρίς απάντηση, αλλάξτε μια υπηρεσία ή ετοιμάστε οικονομική αναφορά. Η ίδια διεπαφή υπάρχει και στο Telegram.' },
    'operator-overview': { title: 'Επισκόπηση τρέχουσας επιχείρησης', body: 'Ο Operator γνωρίζει την κατάσταση της επιλεγμένης επιχείρησης και χρησιμοποιεί αυτά τα δεδομένα στις εργασίες σας. Εδώ εμφανίζονται οι δείκτες που χρειάζονται προσοχή τώρα.' },
    'network-switcher': { title: 'Επιλογή επιχείρησης', body: 'Αν έχετε πολλά σημεία, αλλάξτε γρήγορα μεταξύ τους εδώ. Όλα τα δεδομένα, οι προτάσεις και οι ενέργειες του LocalOS θα αφορούν την επιλεγμένη επιχείρηση.' },
    'progress-nav': { title: 'Πρόοδος επιχείρησης', body: 'Το LocalOS συγκεντρώνει την εξέλιξη σε χάρτες και φήμη, περιεχόμενο, συνεργασίες, αυτοματοποίηση και πρόσθετες πωλήσεις. Κάθε τομέας δείχνει τα ολοκληρωμένα στάδια, το τρέχον πρόβλημα και το επόμενο πρακτικό βήμα.' },
    'progress-overview': { title: 'Επιβεβαιωμένη πρόοδος', body: 'Οι αριθμοί προέρχονται από πραγματικά δεδομένα του LocalOS: συνδεδεμένες καταχωρίσεις, έτοιμο υλικό, συνεργάτες, εκτελέσεις agents και εφαρμοσμένες πρόσθετες πωλήσεις. Δείτε άμεσα τι ολοκληρώθηκε και πού χρειάζεται προσοχή.' },
    'progress-focus-action': { title: 'Η σημαντικότερη προτεραιότητα τώρα', body: 'Το LocalOS συγκρίνει προβλήματα και εκκρεμότητες από όλους τους τομείς και επιλέγει μία προτεραιότητα. Η κάρτα εξηγεί τον λόγο, το αναμενόμενο αποτέλεσμα και ανοίγει το σωστό σημείο εργασίας.' },
    'progress-areas': { title: 'Τομείς και στάδια ανάπτυξης', body: 'Οι τομείς ανάπτυξης εμφανίζονται παρακάτω. Χάρτες, περιεχόμενο, συνεργασίες, αυτοματοποίηση και πρόσθετες πωλήσεις παρακολουθούνται χωριστά. Ανοίξτε μια γραμμή για επιβεβαιωμένα στάδια, τρέχον πρόβλημα, επόμενο αποτέλεσμα και ενέργεια.' },
    'progress-maps': { title: 'Χάρτες και φήμη', body: 'Τα δεδομένα προέρχονται από πρόσφατες συλλογές καταχωρίσεων, ελέγχους, υπηρεσίες και κριτικές. Αναπτύξτε τον τομέα για στάδια και δείκτες και ανοίξτε τον πλήρη έλεγχο για συγκεκριμένες προτάσεις.' },
    'progress-recent-results': { title: 'Πρόσφατα αποτελέσματα', body: 'Εδώ αποθηκεύονται επιβεβαιωμένα γεγονότα με ημερομηνία: ολοκληρωμένος έλεγχος, πλάνο περιεχομένου, πρόταση συνεργασίας, εργασία agent ή εφαρμοσμένη πρόσθετη πώληση. Είναι ιστορικό πραγματικής δουλειάς, όχι λίστα συμβουλών.' },
    'card-nav': { title: 'Καταχώριση στους χάρτες', body: 'Η ενότητα συγκεντρώνει βαθμολογία, κριτικές, υπηρεσίες, φωτογραφίες και ορατότητα στους χάρτες.' },
    'card-overview': { title: 'Εργασία με χάρτες', body: 'Δείτε δεδομένα από συνδεδεμένες πηγές: βαθμολογία, κριτικές, υπηρεσίες, νέα, αναζητήσεις και ανταγωνιστές. Η ανανέωση δεδομένων είναι απενεργοποιημένη στο demo.' },
    'card-services': { title: 'Υπηρεσίες', body: 'Στο «Roga i Kopyta» έχουν φορτωθεί 101 υπηρεσίες. Το LocalOS βρίσκει διπλότυπα, αδύναμους τίτλους και ελλιπείς περιγραφές.' },
    'card-reviews': { title: 'Κριτικές', body: 'Εδώ συγκεντρώνονται οι κριτικές από τους χάρτες. Το LocalOS επισημαίνει όσες δεν έχουν απάντηση και βοηθά να ετοιμάσετε πρόχειρο, ενώ η δημοσίευση παραμένει στον έλεγχό σας.' },
    'card-news': { title: 'Νέα', body: 'Ετοιμάστε νέο για την καταχώριση, ελέγξτε το κείμενο και αποθηκεύστε πρόχειρο. Η δημοσίευση γίνεται μόνο μετά από χειροκίνητη έγκριση.' },
    'card-seo': { title: 'Αναζητήσεις SEO', body: 'Το LocalOS συλλέγει αναζητήσεις και συχνότητα για να δείξει πώς βρίσκουν οι πελάτες τις υπηρεσίες σας και ποια θέματα χρειάζονται ενίσχυση.' },
    'card-competitors': { title: 'Ανταγωνιστές', body: 'Προσθέστε σημαντικές κοντινές καταχωρίσεις για σύγκριση βαθμολογίας, κριτικών και ενεργειών ανταγωνιστών και εκτελέστε στοχευμένο έλεγχο όταν χρειάζεται.' },
    'telegram-radar': { title: 'Ραντάρ Telegram', body: 'Το ραντάρ συλλέγει σήματα από επιλεγμένες πηγές Telegram. Ανοίξτε ένα μήνυμα, κρατήστε το ως ιδέα, ετοιμάστε απάντηση ή αποκρύψτε το.' },
    'average-ticket': { title: 'Πρόσθετες πωλήσεις', body: 'Το LocalOS χρησιμοποιεί στατιστικά της επιχείρησης για να προτείνει πακέτα, διασταυρούμενες πωλήσεις και πρακτικά σενάρια αύξησης της μέσης απόδειξης.' },
    'geo-promotion': { title: 'Προώθηση GEO', body: 'Ελέγξτε την ορατότητα της επιχείρησης στις απαντήσεις υπηρεσιών AI και βρείτε ποια στοιχεία και υλικά χρειάζονται ενίσχυση.' },
    'content-nav': { title: 'Το περιεχόμενο περνά από έλεγχο', body: 'Το ημερολόγιο κρατά θέματα, πρόχειρα και καταστάσεις. Η δημοσίευση παραμένει πάντα χειροκίνητη απόφαση.' },
    'content-calendar': { title: 'Έτοιμο πλάνο περιεχομένου', body: 'Ανοίξτε το επόμενο υλικό και δείτε πώς μια ιδέα γίνεται πρόχειρο. Τα κουμπιά έγκρισης δεν αλλάζουν δεδομένα στο demo.' },
    'partnership-nav': { title: 'Συνεργασίες σε στάδια', body: 'Υποψήφιοι, επιλογή, μηνύματα, αποστολή και απαντήσεις παραμένουν σε ξεχωριστά στάδια.' },
    'partnership-workspace': { title: 'Από υποψήφιο σε συνομιλία', body: 'Στο demo υπάρχουν ήδη συνεργάτες και ιστορικό καμπάνιας. Όλες οι εξερχόμενες ενέργειες είναι απενεργοποιημένες.' },
    'partnership-candidates': { title: 'Η ιστορία με τη «Romashka»', body: 'Η κάρτα συνεργάτη κρατά μαζί το πλαίσιο, την πρόταση, το κανάλι επικοινωνίας και την επόμενη ενέργεια.' },
    finish: { title: 'Η ξενάγηση ολοκληρώθηκε', body: 'Τώρα μπορείτε να ανοίξετε το ψηφιακό δωμάτιο της Romashka και να δείτε την πρόταση όπως ένας υποψήφιος πελάτης. Ή δημιουργήστε λογαριασμό και προσθέστε πραγματική επιχείρηση.' },
  },
  entry: { pageTitle: 'Διαδραστικό demo LocalOS', openingTitle: 'Άνοιγμα του «Roga i Kopyta»', preparing: 'Ετοιμάζουμε την προσωπική σας συνεδρία demo. Τα δεδομένα του λογαριασμού δεν θα αλλάξουν.', unavailable: 'Το demo δεν είναι διαθέσιμο τώρα', openFailed: 'Δεν ήταν δυνατό το άνοιγμα του demo', retry: 'Δοκιμάστε ξανά', loading: 'Φόρτωση παρουσίασης', robotAlt: 'Ρομπότ LocalOS' },
  welcome: { eyebrow: 'Διαδραστικό demo LocalOS', headline: 'Αποκτήστε περισσότερους πελάτες από χάρτες, κριτικές και κοινωνικά δίκτυα — χωρίς επαναλαμβανόμενη χειροκίνητη δουλειά', intro: 'Το LocalOS βοηθά μικρές επιχειρήσεις να διαχειρίζονται Yandex Maps, 2GIS και Google, να απαντούν σε κριτικές, να ετοιμάζουν αναρτήσεις και νέα, να παρακολουθούν κοντινούς ανταγωνιστές και να κατανοούν τι επηρεάζει αιτήματα, έσοδα και μέση απόδειξη.', capabilitiesTitle: 'Τι μπορείτε να κάνετε στο LocalOS', capabilities: ['Δείτε τι χρειάζεται διόρθωση στην καταχώριση', 'Βελτιώστε υπηρεσίες, περιγραφές, φωτογραφίες και νέα', 'Απαντήστε σε κριτικές και βελτιώστε τη βαθμολογία', 'Ετοιμάστε αναρτήσεις χωρίς να ψάχνετε θέμα', 'Δείτε τι κάνουν οι κοντινοί ανταγωνιστές', 'Βρείτε συνεργάτες με παρόμοιο κοινό', 'Αναθέστε επαναλαμβανόμενες εργασίες με απλή γλώσσα'] },
  controls: { progressSaveError: 'Δεν ήταν δυνατή η αποθήκευση της προόδου. Δοκιμάστε ξανά.', launcherOpenAgain: 'Ανοίξτε ξανά την ξενάγηση', launcherContinue: 'Συνεχίστε την ξενάγηση', start: 'Έναρξη ξενάγησης', tourLabel: 'Διαδραστική ξενάγηση LocalOS', robotAlt: 'Ρομπότ LocalOS', robotSuccessAlt: 'Το ρομπότ LocalOS ολοκλήρωσε την ξενάγηση', stepTemplate: 'Βήμα {current} από {total}', pauseLabel: 'Παύση ξενάγησης', progressTemplate: 'Πρόοδος {percent}%', targetMissing: 'Το στοιχείο δεν έχει φορτωθεί ακόμη. Επισημάνετέ το ξανά ή συνεχίστε.', openRoom: 'Άνοιγμα δωματίου', createAccount: 'Δημιουργία λογαριασμού', finish: 'Ολοκλήρωση ξενάγησης', restart: 'Από την αρχή', highlight: 'Επισήμανση στη σελίδα', previous: 'Προηγούμενο βήμα', next: 'Επόμενο', pause: 'Παύση', skip: 'Παράλειψη ξενάγησης' },
  banner: { notice: 'Λειτουργία demo · τα δεδομένα δεν αλλάζουν', createAccount: 'Δημιουργήστε λογαριασμό' },
};

const de: GuidedTourCopy = {
  chapters: { 'network-pulse': 'LocalOS-Leitfaden', 'card-content': 'Eintrag und Inhalte', partnership: 'Partnerschaften' },
  steps: {
    welcome: { title: 'Ich zeige Ihnen alles', body: 'In 8–10 Minuten sehen wir uns Netzwerk, Karteneintrag, Inhalte und Partnerschaften an. Erkunden Sie das Dashboard frei und kehren Sie jederzeit zur Tour zurück.' },
    'operator-nav': { title: 'Operator — Steuerung per Chat', body: 'Steuern Sie LocalOS mit normalen Nachrichten: Beitrag erstellen, unbeantwortete Bewertungen finden, eine Leistung ändern oder einen Finanzbericht vorbereiten. Dieselbe Oberfläche gibt es in Telegram.' },
    'operator-overview': { title: 'Übersicht des aktuellen Unternehmens', body: 'Der Operator kennt den Zustand des gewählten Unternehmens und nutzt diese Daten für Ihre Aufgaben. Hier sehen Sie Kennzahlen, die jetzt Aufmerksamkeit brauchen.' },
    'network-switcher': { title: 'Unternehmen auswählen', body: 'Wenn Sie mehrere Standorte haben, wechseln Sie hier schnell zwischen ihnen. Danach beziehen sich alle Daten, Empfehlungen und Aktionen von LocalOS auf das gewählte Unternehmen.' },
    'progress-nav': { title: 'Unternehmensfortschritt', body: 'LocalOS bündelt die Entwicklung bei Karten und Reputation, Inhalten, Partnerschaften, Automatisierung und Zusatzverkäufen. Jeder Bereich zeigt abgeschlossene Stufen, das aktuelle Problem und den nächsten wirksamen Schritt.' },
    'progress-overview': { title: 'Bestätigter Fortschritt', body: 'Die Zahlen stammen aus echten LocalOS-Daten: verbundene Einträge, fertige Materialien, Partner, Agentenläufe und umgesetzte Zusatzverkäufe. Sehen Sie sofort, was abgeschlossen ist und wo Handlungsbedarf besteht.' },
    'progress-focus-action': { title: 'Jetzt am wichtigsten', body: 'LocalOS vergleicht Probleme und offene Aufgaben aller Bereiche und wählt eine Priorität. Der Block erklärt den Grund, das erwartete Ergebnis und öffnet den passenden Arbeitsbereich.' },
    'progress-areas': { title: 'Wachstumsbereiche und Stufen', body: 'Die Wachstumsbereiche stehen unten. Karten, Inhalte, Partnerschaften, Automatisierung und Zusatzverkäufe werden getrennt verfolgt. Öffnen Sie eine Zeile für bestätigte Stufen, aktuelles Problem, nächstes Ergebnis und Aktion.' },
    'progress-maps': { title: 'Karten und Reputation', body: 'Die Daten kommen aus aktuellen Eintragserfassungen, Audits, Leistungen und Bewertungen. Klappen Sie den Bereich auf, um Stufen und Kennzahlen zu sehen, und öffnen Sie dann das vollständige Audit mit konkreten Empfehlungen.' },
    'progress-recent-results': { title: 'Aktuelle Ergebnisse', body: 'Hier werden bestätigte Ereignisse mit Datum gespeichert: fertiges Audit, Inhaltsplan, Partnerangebot, erledigte Agentenaufgabe oder umgesetzter Zusatzverkauf. Das ist die Historie tatsächlich erledigter Arbeit, keine Ratgeberliste.' },
    'card-nav': { title: 'Karteneintrag', body: 'Dieser Bereich bündelt Bewertung, Rezensionen, Leistungen, Fotos und Sichtbarkeit auf Karten.' },
    'card-overview': { title: 'Mit Karten arbeiten', body: 'Sehen Sie Eintragsdaten aus verbundenen Quellen: Bewertung, Rezensionen, Leistungen, Neuigkeiten, Suchanfragen und Wettbewerber. Die Datenaktualisierung ist in der Demo deaktiviert.' },
    'card-services': { title: 'Leistungen', body: 'Für „Roga i Kopyta“ sind 101 Leistungen geladen. LocalOS findet Duplikate, schwache Namen und fehlende Beschreibungen.' },
    'card-reviews': { title: 'Bewertungen', body: 'Hier stehen Bewertungen von Kartenplattformen. LocalOS markiert unbeantwortete Beiträge und hilft beim Entwurf; die Veröffentlichung bleibt unter Ihrer Kontrolle.' },
    'card-news': { title: 'Neuigkeiten', body: 'Bereiten Sie eine Nachricht für den Unternehmenseintrag vor, prüfen Sie den Text und speichern Sie einen Entwurf. Veröffentlicht wird nur nach manueller Bestätigung.' },
    'card-seo': { title: 'SEO-Suchanfragen', body: 'LocalOS sammelt Suchanfragen und Häufigkeiten, um zu zeigen, wie Kunden nach Ihren Leistungen suchen und welche Themen gestärkt werden sollten.' },
    'card-competitors': { title: 'Wettbewerber', body: 'Fügen Sie wichtige Einträge in der Nähe hinzu, vergleichen Sie Bewertungen, Rezensionen und Aktivitäten und starten Sie bei Bedarf ein gezieltes Audit.' },
    'telegram-radar': { title: 'Telegram-Radar', body: 'Der Radar sammelt Signale aus ausgewählten Telegram-Quellen. Öffnen Sie eine gefundene Nachricht, speichern Sie sie als Idee, bereiten Sie eine Antwort vor oder blenden Sie sie aus.' },
    'average-ticket': { title: 'Zusatzverkäufe', body: 'LocalOS nutzt Unternehmensstatistiken, um Pakete, Cross-Selling und praktische Wege zur Erhöhung des Durchschnittsbon vorzuschlagen.' },
    'geo-promotion': { title: 'GEO-Promotion', body: 'Prüfen Sie die Sichtbarkeit des Unternehmens in Antworten von KI-Diensten und erkennen Sie, welche Fakten und Materialien gestärkt werden müssen.' },
    'content-nav': { title: 'Inhalte werden geprüft', body: 'Der Kalender speichert Themen, Entwürfe und Status. Die Veröffentlichung bleibt immer eine manuelle Entscheidung.' },
    'content-calendar': { title: 'Vorbereiteter Inhaltsplan', body: 'Öffnen Sie den nächsten Inhalt und sehen Sie, wie aus einer Idee ein Entwurf wird. Freigabeschaltflächen ändern in der Demo keine Daten.' },
    'partnership-nav': { title: 'Partnerschaften in Etappen', body: 'Kandidaten, Auswahl, Nachrichten, Versand und Antworten bleiben in getrennten Phasen.' },
    'partnership-workspace': { title: 'Vom Kandidaten zum Gespräch', body: 'Partner und Kampagnenverlauf sind für die Demo bereits vorbereitet. Alle ausgehenden Aktionen sind deaktiviert.' },
    'partnership-candidates': { title: 'Die Geschichte mit „Romashka“', body: 'Die Partnerkarte hält Kontext, Angebot, Kontaktkanal und nächste Aktion zusammen.' },
    finish: { title: 'Tour abgeschlossen', body: 'Öffnen Sie jetzt Romashkas digitalen Raum und betrachten Sie das Angebot aus Sicht eines Leads. Oder erstellen Sie ein eigenes Konto und fügen Sie ein echtes Unternehmen hinzu.' },
  },
  entry: { pageTitle: 'Interaktive LocalOS-Demo', openingTitle: '„Roga i Kopyta“ wird geöffnet', preparing: 'Ihre persönliche Demo-Sitzung wird vorbereitet. Kontodaten werden nicht verändert.', unavailable: 'Die Demo ist derzeit nicht verfügbar', openFailed: 'Die Demo konnte nicht geöffnet werden', retry: 'Erneut versuchen', loading: 'Präsentation wird geladen', robotAlt: 'LocalOS-Roboter' },
  welcome: { eyebrow: 'Interaktive LocalOS-Demo', headline: 'Mehr Kunden über Karten, Bewertungen und soziale Medien — ohne wiederkehrende Handarbeit', intro: 'LocalOS hilft kleinen Unternehmen, Yandex Maps, 2GIS und Google zu verwalten, Bewertungen zu beantworten, Beiträge und Neuigkeiten vorzubereiten, Wettbewerber in der Nähe zu beobachten und zu verstehen, was Anfragen, Umsatz und Durchschnittsbon beeinflusst.', capabilitiesTitle: 'Was Sie in LocalOS tun können', capabilities: ['Erkennen, was am Unternehmenseintrag zu verbessern ist', 'Leistungen, Beschreibungen, Fotos und Neuigkeiten verbessern', 'Bewertungen beantworten und die Bewertung steigern', 'Social-Media-Beiträge ohne Themensuche vorbereiten', 'Aktivitäten naher Wettbewerber beobachten', 'Partner mit ähnlicher Zielgruppe finden', 'Wiederkehrende Aufgaben in Alltagssprache delegieren'] },
  controls: { progressSaveError: 'Der Fortschritt konnte nicht gespeichert werden. Versuchen Sie es erneut.', launcherOpenAgain: 'Tour erneut öffnen', launcherContinue: 'Tour fortsetzen', start: 'Tour starten', tourLabel: 'Interaktive LocalOS-Tour', robotAlt: 'LocalOS-Roboter', robotSuccessAlt: 'Der LocalOS-Roboter hat die Tour beendet', stepTemplate: 'Schritt {current} von {total}', pauseLabel: 'Tour pausieren', progressTemplate: 'Fortschritt {percent} %', targetMissing: 'Dieses Element ist noch nicht geladen. Markieren Sie es erneut oder fahren Sie fort.', openRoom: 'Raum öffnen', createAccount: 'Konto erstellen', finish: 'Tour beenden', restart: 'Neu starten', highlight: 'Auf der Seite markieren', previous: 'Vorheriger Schritt', next: 'Weiter', pause: 'Pause', skip: 'Tour überspringen' },
  banner: { notice: 'Demo-Modus · Daten werden nicht verändert', createAccount: 'Eigenes Konto erstellen' },
};

const th: GuidedTourCopy = {
  chapters: { 'network-pulse': 'คู่มือ LocalOS', 'card-content': 'โปรไฟล์และเนื้อหา', partnership: 'พันธมิตร' },
  steps: {
    welcome: { title: 'ฉันจะพาคุณชมระบบ', body: 'ภายใน 8–10 นาที เราจะดูเครือข่าย โปรไฟล์บนแผนที่ เนื้อหา และพันธมิตร คุณสามารถสำรวจแดชบอร์ดได้อย่างอิสระและกลับมาทัวร์ได้ทุกเมื่อ' },
    'operator-nav': { title: 'Operator — จัดการผ่านแชต', body: 'จัดการ LocalOS ด้วยข้อความธรรมดา เช่น สร้างโพสต์ ค้นหารีวิวที่ยังไม่ได้ตอบ แก้ไขบริการ หรือเตรียมรายงานการเงิน อินเทอร์เฟซเดียวกันมีใน Telegram' },
    'operator-overview': { title: 'ภาพรวมธุรกิจปัจจุบัน', body: 'Operator รู้สถานะของธุรกิจที่เลือกและใช้ข้อมูลนี้ทำงานให้คุณ ที่นี่จะแสดงตัวชี้วัดที่ต้องใส่ใจในตอนนี้' },
    'network-switcher': { title: 'เลือกธุรกิจ', body: 'หากมีหลายสาขา คุณสามารถสลับได้อย่างรวดเร็ว ข้อมูล คำแนะนำ และการทำงานทั้งหมดของ LocalOS จะอ้างอิงธุรกิจที่เลือก' },
    'progress-nav': { title: 'ความคืบหน้าของธุรกิจ', body: 'LocalOS รวมการเติบโตด้านแผนที่และชื่อเสียง เนื้อหา พันธมิตร ระบบอัตโนมัติ และการขายเพิ่ม แต่ละด้านแสดงขั้นที่เสร็จแล้ว ปัญหาปัจจุบัน และขั้นต่อไปที่ให้ผลลัพธ์จริง' },
    'progress-overview': { title: 'ความคืบหน้าที่ตรวจสอบแล้ว', body: 'ตัวเลขมาจากข้อมูลจริงใน LocalOS ได้แก่ โปรไฟล์ที่เชื่อมต่อ สื่อที่เตรียมไว้ พันธมิตร การทำงานของเอเจนต์ และการขายเพิ่มที่นำไปใช้ คุณจะเห็นได้ทันทีว่าส่วนใดเสร็จแล้วและส่วนใดต้องใส่ใจ' },
    'progress-focus-action': { title: 'สิ่งสำคัญที่สุดตอนนี้', body: 'LocalOS เปรียบเทียบปัญหาและงานค้างจากทุกด้านแล้วเลือกหนึ่งเรื่องสำคัญ การ์ดจะแสดงเหตุผล ผลลัพธ์ที่คาดหวัง และเปิดจุดทำงานที่ถูกต้อง' },
    'progress-areas': { title: 'ด้านและขั้นการเติบโต', body: 'ด้านการเติบโตแสดงอยู่ด้านล่าง แผนที่ เนื้อหา พันธมิตร ระบบอัตโนมัติ และการขายเพิ่มถูกติดตามแยกกัน เปิดแต่ละแถวเพื่อดูขั้นที่ยืนยันแล้ว ปัญหาปัจจุบัน ผลลัพธ์ถัดไป และการดำเนินการ' },
    'progress-maps': { title: 'แผนที่และชื่อเสียง', body: 'ข้อมูลมาจากการเก็บโปรไฟล์ การตรวจสอบ บริการ และรีวิวล่าสุด เปิดด้านนี้เพื่อดูขั้นและตัวชี้วัด แล้วเปิดการตรวจสอบฉบับเต็มเพื่อรับคำแนะนำเฉพาะเจาะจง' },
    'progress-recent-results': { title: 'ผลลัพธ์ล่าสุด', body: 'เหตุการณ์ที่ยืนยันแล้วพร้อมวันที่จะอยู่ที่นี่ เช่น การตรวจสอบที่เสร็จ แผนเนื้อหา ข้อเสนอพันธมิตร งานเอเจนต์ หรือการขายเพิ่มที่นำไปใช้ นี่คือประวัติงานที่ทำจริง ไม่ใช่เพียงรายการคำแนะนำ' },
    'card-nav': { title: 'โปรไฟล์บนแผนที่', body: 'ส่วนนี้รวมคะแนน รีวิว บริการ รูปภาพ และการมองเห็นบนแผนที่' },
    'card-overview': { title: 'การทำงานกับแผนที่', body: 'ดูข้อมูลจากแหล่งที่เชื่อมต่อ: คะแนน รีวิว บริการ ข่าว คำค้นหา และคู่แข่ง การอัปเดตข้อมูลถูกปิดในเดโม' },
    'card-services': { title: 'บริการ', body: '“Roga i Kopyta” มีบริการ 101 รายการ LocalOS ค้นหารายการซ้ำ ชื่อที่ไม่ชัดเจน และคำอธิบายที่ขาดหาย' },
    'card-reviews': { title: 'รีวิว', body: 'รีวิวจากแพลตฟอร์มแผนที่รวมอยู่ที่นี่ LocalOS ชี้รีวิวที่ยังไม่ได้ตอบและช่วยเตรียมฉบับร่าง ส่วนการเผยแพร่ยังอยู่ในการควบคุมของคุณ' },
    'card-news': { title: 'ข่าวสาร', body: 'เตรียมข่าวสำหรับโปรไฟล์ธุรกิจ ตรวจข้อความ และบันทึกฉบับร่าง การเผยแพร่จะเกิดขึ้นหลังการยืนยันด้วยตนเองเท่านั้น' },
    'card-seo': { title: 'คำค้นหา SEO', body: 'LocalOS รวบรวมคำค้นหาและความถี่เพื่อแสดงว่าลูกค้าค้นหาบริการของคุณอย่างไร และควรเสริมเรื่องใด' },
    'card-competitors': { title: 'คู่แข่ง', body: 'เพิ่มโปรไฟล์สำคัญใกล้เคียงเพื่อเปรียบเทียบคะแนน รีวิว และกิจกรรมของคู่แข่ง แล้วตรวจสอบเฉพาะจุดเมื่อจำเป็น' },
    'telegram-radar': { title: 'เรดาร์ Telegram', body: 'เรดาร์รวบรวมสัญญาณจากแหล่ง Telegram ที่เลือก เปิดข้อความที่พบ บันทึกเป็นไอเดีย เตรียมคำตอบ หรือซ่อนได้' },
    'average-ticket': { title: 'การขายเพิ่ม', body: 'LocalOS ใช้สถิติธุรกิจเพื่อแนะนำแพ็กเกจ การขายข้าม และแนวทางที่ใช้งานได้เพื่อเพิ่มยอดใช้จ่ายเฉลี่ย' },
    'geo-promotion': { title: 'การโปรโมต GEO', body: 'ตรวจสอบว่าธุรกิจปรากฏในคำตอบของบริการ AI มากน้อยเพียงใด และระบุข้อมูลหรือสื่อที่ควรเสริม' },
    'content-nav': { title: 'เนื้อหาผ่านการตรวจสอบ', body: 'ปฏิทินเก็บหัวข้อ ฉบับร่าง และสถานะ การเผยแพร่ยังคงเป็นการตัดสินใจด้วยตนเองเสมอ' },
    'content-calendar': { title: 'แผนเนื้อหาที่เตรียมไว้', body: 'เปิดเนื้อหาถัดไปและดูว่าไอเดียกลายเป็นฉบับร่างอย่างไร ปุ่มอนุมัติจะไม่เปลี่ยนข้อมูลในเดโม' },
    'partnership-nav': { title: 'พันธมิตรทำงานเป็นขั้นตอน', body: 'ผู้สมัคร การคัดเลือก ข้อความ การส่ง และคำตอบถูกแยกเป็นแต่ละขั้นอย่างชัดเจน' },
    'partnership-workspace': { title: 'จากผู้สมัครสู่การสนทนา', body: 'เดโมเตรียมพันธมิตรและประวัติแคมเปญไว้แล้ว การดำเนินการส่งออกทั้งหมดถูกปิด' },
    'partnership-candidates': { title: 'เรื่องราวกับ “Romashka”', body: 'การ์ดพันธมิตรเก็บบริบท ข้อเสนอ ช่องทางติดต่อ และการดำเนินการถัดไปไว้ด้วยกัน' },
    finish: { title: 'จบทัวร์แล้ว', body: 'ตอนนี้คุณสามารถเปิดห้องดิจิทัลของ Romashka และดูข้อเสนอในมุมของลีด หรือสร้างบัญชีของคุณและเพิ่มธุรกิจจริง' },
  },
  entry: { pageTitle: 'เดโม LocalOS แบบโต้ตอบ', openingTitle: 'กำลังเปิด “Roga i Kopyta”', preparing: 'กำลังเตรียมเซสชันเดโมส่วนตัว ข้อมูลบัญชีจะไม่ถูกเปลี่ยน', unavailable: 'เดโมไม่พร้อมใช้งานในขณะนี้', openFailed: 'ไม่สามารถเปิดเดโมได้', retry: 'ลองอีกครั้ง', loading: 'กำลังโหลดตัวอย่าง', robotAlt: 'หุ่นยนต์ LocalOS' },
  welcome: { eyebrow: 'เดโม LocalOS แบบโต้ตอบ', headline: 'รับลูกค้าเพิ่มจากแผนที่ รีวิว และโซเชียลมีเดีย โดยไม่ต้องทำงานซ้ำด้วยตนเอง', intro: 'LocalOS ช่วยเจ้าของธุรกิจขนาดเล็กจัดการ Yandex Maps, 2GIS และ Google ตอบรีวิว เตรียมโพสต์และข่าว ติดตามคู่แข่งใกล้เคียง และเข้าใจสิ่งที่ส่งผลต่อคำขอ รายได้ และยอดใช้จ่ายเฉลี่ย', capabilitiesTitle: 'สิ่งที่คุณทำได้ใน LocalOS', capabilities: ['ดูว่าต้องแก้อะไรในโปรไฟล์ธุรกิจ', 'ปรับปรุงบริการ คำอธิบาย รูปภาพ และข่าว', 'ตอบรีวิวและเพิ่มคะแนน', 'เตรียมโพสต์โดยไม่ต้องคิดว่าจะโพสต์อะไร', 'ดูว่าคู่แข่งใกล้เคียงทำอะไร', 'ค้นหาพันธมิตรที่มีกลุ่มเป้าหมายคล้ายกัน', 'มอบหมายงานซ้ำด้วยภาษาธรรมดา'] },
  controls: { progressSaveError: 'บันทึกความคืบหน้าไม่ได้ โปรดลองอีกครั้ง', launcherOpenAgain: 'เปิดทัวร์อีกครั้ง', launcherContinue: 'ทัวร์ต่อ', start: 'เริ่มทัวร์', tourLabel: 'ทัวร์ LocalOS แบบโต้ตอบ', robotAlt: 'หุ่นยนต์ LocalOS', robotSuccessAlt: 'หุ่นยนต์ LocalOS จบทัวร์แล้ว', stepTemplate: 'ขั้นที่ {current} จาก {total}', pauseLabel: 'หยุดทัวร์ชั่วคราว', progressTemplate: 'ความคืบหน้า {percent}%', targetMissing: 'องค์ประกอบนี้ยังไม่โหลด ลองเน้นอีกครั้งหรือไปขั้นถัดไป', openRoom: 'เปิดห้อง', createAccount: 'สร้างบัญชี', finish: 'จบทัวร์', restart: 'เริ่มใหม่', highlight: 'เน้นบนหน้า', previous: 'ขั้นก่อนหน้า', next: 'ถัดไป', pause: 'หยุดชั่วคราว', skip: 'ข้ามทัวร์' },
  banner: { notice: 'โหมดเดโม · ข้อมูลจะไม่ถูกเปลี่ยน', createAccount: 'สร้างบัญชีของคุณ' },
};

const ar: GuidedTourCopy = {
  chapters: { 'network-pulse': 'دليل LocalOS', 'card-content': 'بطاقة النشاط والمحتوى', partnership: 'الشراكات' },
  steps: {
    welcome: { title: 'سأساعدك على التعرّف إلى النظام', body: 'خلال 8–10 دقائق سنراجع الشبكة وبطاقة النشاط على الخرائط والمحتوى والشراكات. يمكنك استكشاف لوحة التحكم بحرية والعودة إلى الجولة في أي وقت.' },
    'operator-nav': { title: 'المشغّل — إدارة عبر المحادثة', body: 'أدر LocalOS برسائل عادية: أنشئ منشورًا، وابحث عن مراجعات بلا رد، وعدّل خدمة، أو جهّز تقريرًا ماليًا. الواجهة نفسها متاحة في Telegram.' },
    'operator-overview': { title: 'نظرة عامة على النشاط الحالي', body: 'يعرف المشغّل حالة النشاط المحدد ويستخدم هذه البيانات عند تنفيذ مهامك. تظهر هنا المؤشرات التي تحتاج إلى اهتمام الآن.' },
    'network-switcher': { title: 'اختيار النشاط', body: 'إذا كانت لديك عدة فروع، يمكنك التنقل بينها بسرعة هنا. بعد الاختيار ستتعلق كل بيانات LocalOS وتوصياته وإجراءاته بهذا النشاط.' },
    'progress-nav': { title: 'تقدم النشاط', body: 'يجمع LocalOS التطور في الخرائط والسمعة والمحتوى والشراكات والأتمتة والمبيعات الإضافية. يعرض كل مجال المراحل المكتملة والمشكلة الحالية والخطوة التالية ذات النتيجة العملية.' },
    'progress-overview': { title: 'تقدم موثّق', body: 'تأتي الأرقام من بيانات LocalOS الفعلية: البطاقات المتصلة والمواد الجاهزة والشركاء وتشغيل الوكلاء والمبيعات الإضافية المطبقة. اعرف سريعًا ما اكتمل وما يحتاج إلى اهتمام.' },
    'progress-focus-action': { title: 'الأهم الآن', body: 'يقارن LocalOS المشكلات والمهام غير المكتملة في كل المجالات ويختار أولوية واحدة. تشرح البطاقة السبب والنتيجة المتوقعة وتفتح مكان العمل المناسب.' },
    'progress-areas': { title: 'مجالات ومراحل النمو', body: 'تظهر مجالات النمو أدناه. تتم متابعة الخرائط والمحتوى والشراكات والأتمتة والمبيعات الإضافية كلٌ على حدة. افتح صفًا لرؤية المراحل الموثقة والمشكلة الحالية والنتيجة التالية والإجراء.' },
    'progress-maps': { title: 'الخرائط والسمعة', body: 'تأتي البيانات من أحدث عمليات جمع البطاقات والتدقيق والخدمات والمراجعات. وسّع المجال لرؤية المراحل والمؤشرات، ثم افتح التدقيق الكامل للحصول على توصيات محددة.' },
    'progress-recent-results': { title: 'النتائج الأخيرة', body: 'تُحفظ هنا الأحداث الموثقة مع تواريخها: تدقيق مكتمل أو خطة محتوى أو عرض لشريك أو مهمة وكيل منجزة أو بيع إضافي مطبق. هذا سجل لما تم فعله فعليًا، وليس قائمة نصائح.' },
    'card-nav': { title: 'بطاقة النشاط على الخرائط', body: 'يجمع هذا القسم التقييم والمراجعات والخدمات والصور والظهور على الخرائط.' },
    'card-overview': { title: 'العمل مع الخرائط', body: 'اطّلع على بيانات البطاقة من المصادر المتصلة: التقييم والمراجعات والخدمات والأخبار وطلبات البحث والمنافسون. تحديث البيانات معطّل في النسخة التجريبية.' },
    'card-services': { title: 'الخدمات', body: 'يحتوي نشاط «Roga i Kopyta» على 101 خدمة. يعثر LocalOS على التكرارات والأسماء الضعيفة والأوصاف الناقصة.' },
    'card-reviews': { title: 'المراجعات', body: 'تظهر هنا مراجعات منصات الخرائط. يبرز LocalOS المراجعات التي بلا رد ويساعد في إعداد مسودة، بينما يبقى النشر تحت سيطرتك.' },
    'card-news': { title: 'الأخبار', body: 'جهّز خبرًا لبطاقة النشاط وراجع النص واحفظ مسودة. لا يتم النشر إلا بعد موافقة يدوية.' },
    'card-seo': { title: 'استعلامات SEO', body: 'يجمع LocalOS استعلامات البحث وتكرارها ليوضح كيف يبحث العملاء عن خدماتك وما الموضوعات التي ينبغي تعزيزها.' },
    'card-competitors': { title: 'المنافسون', body: 'أضف البطاقات المهمة القريبة لمقارنة التقييمات والمراجعات ونشاط المنافسين، ثم شغّل تدقيقًا مركزًا عند الحاجة.' },
    'telegram-radar': { title: 'رادار Telegram', body: 'يجمع الرادار الإشارات من مصادر Telegram المحددة. افتح رسالة عُثر عليها أو احفظها كفكرة أو جهّز ردًا أو أخفها.' },
    'average-ticket': { title: 'المبيعات الإضافية', body: 'يستخدم LocalOS إحصاءات النشاط لاقتراح الحزم والبيع المتقاطع وسيناريوهات عملية لزيادة متوسط الفاتورة.' },
    'geo-promotion': { title: 'الترويج عبر GEO', body: 'تحقق من ظهور النشاط في إجابات خدمات الذكاء الاصطناعي وحدد الحقائق والمواد التي تحتاج إلى تعزيز.' },
    'content-nav': { title: 'المحتوى يمر بالمراجعة', body: 'يحفظ التقويم الموضوعات والمسودات والحالات. يظل النشر دائمًا قرارًا يدويًا.' },
    'content-calendar': { title: 'خطة محتوى جاهزة', body: 'افتح المادة التالية وشاهد كيف تتحول الفكرة إلى مسودة. أزرار الموافقة لا تغيّر البيانات في النسخة التجريبية.' },
    'partnership-nav': { title: 'الشراكات على مراحل', body: 'يتم فصل المرشحين والاختيار والرسائل والإرسال والردود في مراحل واضحة.' },
    'partnership-workspace': { title: 'من مرشح إلى محادثة', body: 'تم إعداد الشركاء وسجل الحملة مسبقًا للنسخة التجريبية. كل الإجراءات الصادرة معطّلة.' },
    'partnership-candidates': { title: 'القصة مع «Romashka»', body: 'تجمع بطاقة الشريك السياق والعرض وقناة التواصل والإجراء التالي.' },
    finish: { title: 'اكتملت الجولة', body: 'يمكنك الآن فتح الغرفة الرقمية لـ Romashka ورؤية العرض كما يراه العميل المحتمل. أو أنشئ حسابك وأضف نشاطًا حقيقيًا.' },
  },
  entry: { pageTitle: 'نسخة LocalOS التجريبية التفاعلية', openingTitle: 'جارٍ فتح «Roga i Kopyta»', preparing: 'نجهّز جلستك التجريبية الشخصية. لن تتغير بيانات الحساب.', unavailable: 'النسخة التجريبية غير متاحة حاليًا', openFailed: 'تعذر فتح النسخة التجريبية', retry: 'حاول مرة أخرى', loading: 'جارٍ تحميل العرض', robotAlt: 'روبوت LocalOS' },
  welcome: { eyebrow: 'نسخة LocalOS التجريبية التفاعلية', headline: 'احصل على عملاء أكثر من الخرائط والمراجعات والشبكات الاجتماعية — بلا أعمال يدوية متكررة', intro: 'يساعد LocalOS أصحاب الأنشطة الصغيرة على إدارة Yandex Maps و2GIS وGoogle والرد على المراجعات وإعداد المنشورات والأخبار ومتابعة المنافسين القريبين وفهم ما يؤثر في الطلبات والإيرادات ومتوسط الفاتورة.', capabilitiesTitle: 'ما الذي يمكنك فعله في LocalOS', capabilities: ['اعرف ما يجب إصلاحه في بطاقة النشاط', 'حسّن الخدمات والأوصاف والصور والأخبار', 'رد على المراجعات وارفع التقييم', 'جهّز منشورات بلا حيرة حول ما ستنشره', 'تابع ما يفعله المنافسون القريبون', 'اعثر على شركاء لهم جمهور مشابه', 'فوّض المهام المتكررة بلغة بسيطة'] },
  controls: { progressSaveError: 'تعذر حفظ تقدمك. حاول مرة أخرى.', launcherOpenAgain: 'فتح الجولة مرة أخرى', launcherContinue: 'متابعة الجولة', start: 'بدء الجولة', tourLabel: 'جولة LocalOS التفاعلية', robotAlt: 'روبوت LocalOS', robotSuccessAlt: 'أكمل روبوت LocalOS الجولة', stepTemplate: 'الخطوة {current} من {total}', pauseLabel: 'إيقاف الجولة مؤقتًا', progressTemplate: 'التقدم {percent}٪', targetMissing: 'لم يتم تحميل هذا العنصر بعد. يمكنك إبرازه مرة أخرى أو المتابعة.', openRoom: 'فتح الغرفة', createAccount: 'إنشاء حساب', finish: 'إنهاء الجولة', restart: 'البدء من جديد', highlight: 'إبراز في الصفحة', previous: 'الخطوة السابقة', next: 'التالي', pause: 'إيقاف مؤقت', skip: 'تخطي الجولة' },
  banner: { notice: 'الوضع التجريبي · لا يتم تغيير البيانات', createAccount: 'أنشئ حسابك' },
};

const ha: GuidedTourCopy = {
  chapters: { 'network-pulse': 'Jagorar LocalOS', 'card-content': 'Bayanan kasuwanci da abun ciki', partnership: 'Haɗin gwiwa' },
  steps: {
    welcome: { title: 'Zan nuna maka yadda yake aiki', body: 'A cikin mintuna 8–10 za mu duba rassan kasuwanci, bayanin taswira, abun ciki da haɗin gwiwa. Za ka iya bincika dashboard sannan ka dawo yawon a kowane lokaci.' },
    'operator-nav': { title: 'Operator — sarrafawa ta hira', body: 'Sarrafa LocalOS da saƙonni na yau da kullum: ƙirƙiri post, nemo reviews marasa amsa, gyara service ko shirya rahoton kuɗi. Ana samun wannan hanyar a Telegram ma.' },
    'operator-overview': { title: 'Takaitaccen bayanin kasuwancin yanzu', body: 'Operator ya san halin kasuwancin da aka zaɓa kuma yana amfani da bayanan wajen ayyukanka. Nan ne ake nuna ma’aunan da ke bukatar kulawa yanzu.' },
    'network-switcher': { title: 'Zaɓi kasuwanci', body: 'Idan kana da wurare da yawa, ka sauya tsakaninsu a nan. Dukkan bayanai, shawarwari da ayyukan LocalOS za su shafi kasuwancin da aka zaɓa.' },
    'progress-nav': { title: 'Ci gaban kasuwanci', body: 'LocalOS yana haɗa ci gaba a taswira da suna, abun ciki, haɗin gwiwa, automation da ƙarin tallace-tallace. Kowane fanni yana nuna matakan da aka kammala, matsalar yanzu da mataki na gaba mai amfani.' },
    'progress-overview': { title: 'Ci gaban da aka tabbatar', body: 'Lambobin suna fitowa daga bayanan LocalOS na gaske: bayanan taswira da aka haɗa, kayan da aka shirya, abokan hulɗa, ayyukan agents da ƙarin tallace-tallacen da aka aiwatar. Ka ga abin da aka gama da inda ake bukatar kulawa.' },
    'progress-focus-action': { title: 'Abin da ya fi muhimmanci yanzu', body: 'LocalOS yana kwatanta matsaloli da ayyukan da ba a gama ba a duk fannoni sannan ya zaɓi fifiko guda. Kat ɗin yana bayyana dalili, sakamakon da ake sa ran samu da wurin aikin da ya dace.' },
    'progress-areas': { title: 'Fannoni da matakan haɓaka', body: 'An nuna fannonin haɓaka a ƙasa. Taswira, abun ciki, haɗin gwiwa, automation da ƙarin tallace-tallace ana bibiyarsu dabam. Buɗe layi don ganin matakan da aka tabbatar, matsalar yanzu, sakamako na gaba da matakin aiki.' },
    'progress-maps': { title: 'Taswira da suna', body: 'Bayanan suna fitowa daga sabon tattara bayanan kasuwanci, audits, services da reviews. Buɗe fannin don ganin matakai da ma’aunai, sannan ka buɗe cikakken audit domin takamaiman shawarwari.' },
    'progress-recent-results': { title: 'Sakamakon baya-bayan nan', body: 'Ana ajiye abubuwan da aka tabbatar tare da kwanan wata: audit da aka gama, tsarin abun ciki, tayin haɗin gwiwa, aikin agent ko ƙarin tallace-tallace da aka aiwatar. Tarihin aikin da aka yi ne, ba jerin shawarwari kawai ba.' },
    'card-nav': { title: 'Bayanan kasuwanci a taswira', body: 'Wannan sashe yana haɗa rating, reviews, services, hotuna da yadda ake ganin kasuwancin a taswira.' },
    'card-overview': { title: 'Aiki da taswira', body: 'Duba bayanai daga hanyoyin da aka haɗa: rating, reviews, services, labarai, kalmomin bincike da masu gasa. An kashe sabunta bayanai a demo.' },
    'card-services': { title: 'Services', body: '“Roga i Kopyta” yana da services 101. LocalOS yana gano maimaituwa, sunaye marasa ƙarfi da bayanin da bai cika ba.' },
    'card-reviews': { title: 'Reviews', body: 'Ana tara reviews daga taswira a nan. LocalOS yana nuna waɗanda ba a amsa ba kuma yana taimaka shirya draft, amma kai ne ke sarrafa wallafawa.' },
    'card-news': { title: 'Labarai', body: 'Shirya labari don bayanin kasuwanci, duba rubutun kuma adana draft. Ana wallafawa ne kawai bayan amincewar mutum.' },
    'card-seo': { title: 'Binciken SEO', body: 'LocalOS yana tattara kalmomin bincike da yawan amfaninsu domin nuna yadda kwastomomi ke neman services ɗinka da batutuwan da ya kamata a ƙarfafa.' },
    'card-competitors': { title: 'Masu gasa', body: 'Ƙara muhimman bayanan kasuwanci na kusa don kwatanta ratings, reviews da ayyukan masu gasa, sannan ka gudanar da takamaiman audit idan ana bukata.' },
    'telegram-radar': { title: 'Telegram Radar', body: 'Radar yana tattara alamomi daga hanyoyin Telegram da aka zaɓa. Buɗe saƙon da aka samu, adana shi a matsayin ra’ayi, shirya amsa ko ɓoye shi.' },
    'average-ticket': { title: 'Ƙarin tallace-tallace', body: 'LocalOS yana amfani da kididdigar kasuwanci don ba da shawarar packages, cross-sells da hanyoyin aiki na ƙara matsakaicin kuɗin ciniki.' },
    'geo-promotion': { title: 'Tallata GEO', body: 'Duba yadda kasuwancin ke bayyana a amsoshin ayyukan AI kuma gano bayanai da kayan da ya kamata a ƙarfafa.' },
    'content-nav': { title: 'Ana duba abun ciki kafin wallafawa', body: 'Kalanda yana adana batutuwa, drafts da statuses. Wallafawa koyaushe shawarar mutum ce.' },
    'content-calendar': { title: 'Tsarin abun ciki da aka shirya', body: 'Buɗe abu na gaba ka ga yadda ra’ayi yake zama draft. Maɓallan amincewa ba sa canza bayanai a demo.' },
    'partnership-nav': { title: 'Haɗin gwiwa yana tafiya mataki-mataki', body: 'Candidates, zaɓe, saƙonni, aikawa da amsoshi suna cikin matakai dabam.' },
    'partnership-workspace': { title: 'Daga candidate zuwa tattaunawa', body: 'An riga an shirya abokan hulɗa da tarihin campaign don demo. An kashe duk ayyukan aikawa.' },
    'partnership-candidates': { title: 'Labarin “Romashka”', body: 'Kat ɗin abokin hulɗa yana ajiye mahallin, tayin, hanyar sadarwa da mataki na gaba tare.' },
    finish: { title: 'An gama yawon', body: 'Yanzu za ka iya buɗe ɗakin dijital na Romashka ka ga tayin kamar yadda lead zai gani. Ko ka ƙirƙiri asusunka ka ƙara kasuwanci na gaske.' },
  },
  entry: { pageTitle: 'Demo na LocalOS mai hulɗa', openingTitle: 'Ana buɗe “Roga i Kopyta”', preparing: 'Ana shirya zaman demo naka. Ba za a canza bayanan asusu ba.', unavailable: 'Demo ba ya samuwa yanzu', openFailed: 'Ba a iya buɗe demo ba', retry: 'Sake gwadawa', loading: 'Ana loda misali', robotAlt: 'Robot na LocalOS' },
  welcome: { eyebrow: 'Demo na LocalOS mai hulɗa', headline: 'Samu ƙarin kwastomomi daga taswira, reviews da social media — ba tare da maimaita aikin hannu ba', intro: 'LocalOS yana taimaka wa ƙananan kasuwanci su sarrafa Yandex Maps, 2GIS da Google, amsa reviews, shirya posts da labarai, bibiyar masu gasa na kusa da fahimtar abin da ke shafar leads, kuɗin shiga da matsakaicin ciniki.', capabilitiesTitle: 'Abin da za ka iya yi a LocalOS', capabilities: ['Gano abin da za a gyara a bayanin kasuwanci', 'Inganta services, descriptions, hotuna da labarai', 'Amsa reviews da ƙara rating', 'Shirya posts ba tare da neman abin wallafawa ba', 'Duba abin da masu gasa na kusa suke yi', 'Nemo abokan hulɗa masu audience iri ɗaya', 'Ba da ayyukan maimaituwa da yare mai sauƙi'] },
  controls: { progressSaveError: 'Ba a iya adana ci gaba ba. Sake gwadawa.', launcherOpenAgain: 'Sake buɗe yawon', launcherContinue: 'Ci gaba da yawon', start: 'Fara yawon', tourLabel: 'Yawon LocalOS mai hulɗa', robotAlt: 'Robot na LocalOS', robotSuccessAlt: 'Robot na LocalOS ya gama yawon', stepTemplate: 'Mataki {current} cikin {total}', pauseLabel: 'Dakatar da yawon', progressTemplate: 'Ci gaba {percent}%', targetMissing: 'Wannan abu bai loda ba tukuna. Sake haskaka shi ko ka ci gaba.', openRoom: 'Buɗe ɗaki', createAccount: 'Ƙirƙiri asusu', finish: 'Gama yawon', restart: 'Sake farawa', highlight: 'Haskaka a shafi', previous: 'Matakin baya', next: 'Na gaba', pause: 'Dakatar', skip: 'Tsallake yawon' },
  banner: { notice: 'Yanayin demo · ba a canza bayanai', createAccount: 'Ƙirƙiri asusunka' },
};

const tr: GuidedTourCopy = {
  chapters: { 'network-pulse': 'LocalOS rehberi', 'card-content': 'İşletme kartı ve içerik', partnership: 'İş ortaklıkları' },
  steps: {
    welcome: { title: 'Size sistemi tanıtacağım', body: '8–10 dakika içinde ağı, harita kaydını, içeriği ve iş ortaklıklarını inceleyeceğiz. Paneli özgürce keşfedebilir ve tura istediğiniz zaman dönebilirsiniz.' },
    'operator-nav': { title: 'Operatör — sohbetle yönetim', body: 'LocalOS’u normal mesajlarla yönetin: gönderi oluşturun, yanıtsız yorumları bulun, bir hizmeti değiştirin veya finans raporu hazırlayın. Aynı arayüz Telegram’da da kullanılabilir.' },
    'operator-overview': { title: 'Mevcut işletme özeti', body: 'Operatör seçili işletmenin durumunu bilir ve görevlerinizi yürütürken bu verileri kullanır. Şu anda dikkat gerektiren göstergeler burada görünür.' },
    'network-switcher': { title: 'İşletme seçimi', body: 'Birden fazla şubeniz varsa burada hızla aralarında geçiş yapın. Seçimden sonra tüm LocalOS verileri, önerileri ve işlemleri bu işletmeye ait olur.' },
    'progress-nav': { title: 'İşletme ilerlemesi', body: 'LocalOS haritalar ve itibar, içerik, iş ortaklıkları, otomasyon ve ek satışlardaki gelişimi bir araya getirir. Her alan tamamlanan aşamaları, mevcut sorunu ve pratik sonuç sağlayacak sonraki adımı gösterir.' },
    'progress-overview': { title: 'Doğrulanmış ilerleme', body: 'Rakamlar gerçek LocalOS verilerinden gelir: bağlı kayıtlar, hazır materyaller, ortaklar, ajan çalışmaları ve uygulanan ek satışlar. Kaç aşamanın tamamlandığını ve nerede dikkat gerektiğini hızla görün.' },
    'progress-focus-action': { title: 'Şu anda en önemli konu', body: 'LocalOS tüm alanlardaki sorunları ve yarım kalan görevleri karşılaştırarak tek bir öncelik seçer. Kart nedeni, beklenen sonucu açıklar ve doğru çalışma alanını açar.' },
    'progress-areas': { title: 'Büyüme alanları ve aşamaları', body: 'Büyüme alanları aşağıda gösterilir. Haritalar, içerik, iş ortaklıkları, otomasyon ve ek satışlar ayrı izlenir. Doğrulanmış aşamaları, mevcut sorunu, sonraki sonucu ve eylemi görmek için bir satırı açın.' },
    'progress-maps': { title: 'Haritalar ve itibar', body: 'Veriler son işletme kaydı taramalarından, denetimlerden, hizmetlerden ve yorumlardan gelir. Aşamaları ve ölçümleri görmek için alanı açın, ardından somut öneriler için tam denetimi görüntüleyin.' },
    'progress-recent-results': { title: 'Son sonuçlar', body: 'Tarihli ve doğrulanmış olaylar burada tutulur: tamamlanmış denetim, içerik planı, ortaklık teklifi, tamamlanan ajan görevi veya uygulanan ek satış. Bu, öneri listesi değil gerçekten yapılan işlerin geçmişidir.' },
    'card-nav': { title: 'Harita kaydı', body: 'Bu bölüm puanı, yorumları, hizmetleri, fotoğrafları ve harita görünürlüğünü bir araya getirir.' },
    'card-overview': { title: 'Haritalarla çalışma', body: 'Bağlı kaynaklardan işletme kaydı verilerini görün: puan, yorumlar, hizmetler, haberler, arama sorguları ve rakipler. Demo’da veri yenileme kapalıdır.' },
    'card-services': { title: 'Hizmetler', body: '“Roga i Kopyta” için 101 hizmet yüklenmiştir. LocalOS tekrarları, zayıf adları ve eksik açıklamaları bulur.' },
    'card-reviews': { title: 'Yorumlar', body: 'Harita platformlarındaki yorumlar burada toplanır. LocalOS yanıtsız yorumları gösterir ve taslak hazırlamaya yardım eder; yayınlama sizin kontrolünüzde kalır.' },
    'card-news': { title: 'Haberler', body: 'İşletme kaydı için haber hazırlayın, metni kontrol edin ve taslak kaydedin. Yayınlama yalnızca manuel onaydan sonra gerçekleşir.' },
    'card-seo': { title: 'SEO sorguları', body: 'LocalOS müşterilerin hizmetlerinizi hangi ifadelerle aradığını ve hangi konuların güçlendirilmesi gerektiğini göstermek için arama sorgularını ve sıklığını toplar.' },
    'card-competitors': { title: 'Rakipler', body: 'Puanları, yorumları ve rakip faaliyetlerini karşılaştırmak için yakındaki önemli kayıtları ekleyin; gerektiğinde odaklı bir denetim başlatın.' },
    'telegram-radar': { title: 'Telegram Radarı', body: 'Radar seçili Telegram kaynaklarından sinyaller toplar. Bulunan mesajı açın, fikir olarak kaydedin, yanıt hazırlayın veya gizleyin.' },
    'average-ticket': { title: 'Ek satışlar', body: 'LocalOS paketler, çapraz satışlar ve ortalama sepeti artıracak uygulanabilir senaryolar önermek için işletme istatistiklerini kullanır.' },
    'geo-promotion': { title: 'GEO tanıtımı', body: 'İşletmenin yapay zekâ hizmetlerinin yanıtlarındaki görünürlüğünü kontrol edin ve hangi bilgi ve materyallerin güçlendirilmesi gerektiğini belirleyin.' },
    'content-nav': { title: 'İçerik kontrolden geçer', body: 'Takvim konuları, taslakları ve durumları saklar. Yayınlama her zaman manuel bir karar olarak kalır.' },
    'content-calendar': { title: 'Hazırlanmış içerik planı', body: 'Sıradaki içeriği açın ve bir fikrin taslağa nasıl dönüştüğünü görün. Onay düğmeleri demo verilerini değiştirmez.' },
    'partnership-nav': { title: 'İş ortaklıkları aşamalarla ilerler', body: 'Adaylar, seçim, mesajlar, gönderim ve yanıtlar ayrı aşamalarda tutulur.' },
    'partnership-workspace': { title: 'Adaydan görüşmeye', body: 'Demo için ortaklar ve kampanya geçmişi önceden hazırlanmıştır. Tüm giden işlemler kapalıdır.' },
    'partnership-candidates': { title: '“Romashka” ile hikâye', body: 'Ortak kartı bağlamı, teklifi, iletişim kanalını ve sonraki eylemi bir arada tutar.' },
    finish: { title: 'Tur tamamlandı', body: 'Artık Romashka’nın dijital odasını açıp teklifi potansiyel müşterinin gözünden görebilirsiniz. Ya da kendi hesabınızı oluşturup gerçek bir işletme ekleyin.' },
  },
  entry: { pageTitle: 'LocalOS etkileşimli demo', openingTitle: '“Roga i Kopyta” açılıyor', preparing: 'Kişisel demo oturumunuz hazırlanıyor. Hesap verileri değiştirilmeyecek.', unavailable: 'Demo şu anda kullanılamıyor', openFailed: 'Demo açılamadı', retry: 'Tekrar dene', loading: 'Tanıtım yükleniyor', robotAlt: 'LocalOS robotu' },
  welcome: { eyebrow: 'LocalOS etkileşimli demo', headline: 'Haritalardan, yorumlardan ve sosyal medyadan daha fazla müşteri alın — tekrarlayan manuel işler olmadan', intro: 'LocalOS küçük işletme sahiplerinin Yandex Maps, 2GIS ve Google’ı yönetmesine, yorumları yanıtlamasına, gönderi ve haber hazırlamasına, yakındaki rakipleri izlemesine ve talepleri, geliri ve ortalama sepeti nelerin etkilediğini anlamasına yardımcı olur.', capabilitiesTitle: 'LocalOS’ta neler yapabilirsiniz', capabilities: ['İşletme kaydında neyin düzeltilmesi gerektiğini görün', 'Hizmetleri, açıklamaları, fotoğrafları ve haberleri iyileştirin', 'Yorumları yanıtlayın ve puanı yükseltin', 'Ne paylaşacağınızı düşünmeden sosyal medya gönderileri hazırlayın', 'Yakındaki rakiplerin ne yaptığını görün', 'Benzer hedef kitleye sahip ortaklar bulun', 'Tekrarlayan görevleri günlük dille devredin'] },
  controls: { progressSaveError: 'İlerleme kaydedilemedi. Tekrar deneyin.', launcherOpenAgain: 'Turu yeniden aç', launcherContinue: 'Tura devam et', start: 'Turu başlat', tourLabel: 'LocalOS etkileşimli turu', robotAlt: 'LocalOS robotu', robotSuccessAlt: 'LocalOS robotu turu tamamladı', stepTemplate: 'Adım {current} / {total}', pauseLabel: 'Turu duraklat', progressTemplate: 'İlerleme %{percent}', targetMissing: 'Bu öğe henüz yüklenmedi. Yeniden vurgulayabilir veya devam edebilirsiniz.', openRoom: 'Odayı aç', createAccount: 'Hesap oluştur', finish: 'Turu bitir', restart: 'Baştan başla', highlight: 'Sayfada vurgula', previous: 'Önceki adım', next: 'İleri', pause: 'Duraklat', skip: 'Turu atla' },
  banner: { notice: 'Demo modu · veriler değiştirilmez', createAccount: 'Kendi hesabını oluştur' },
};

export const supportedGuidedTourLanguages: Language[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

const copyByLanguage: Record<Language, GuidedTourCopy> = { ru, en, fr, es, el, de, th, ar, ha, tr };

type AutomationTourCopy = { chapter: string; nav: GuidedTourStepText; signals: GuidedTourStepText; today: GuidedTourStepText; employees: GuidedTourStepText; control: GuidedTourStepText };

const automationCopy: Record<Language, AutomationTourCopy> = {
  ru: { chapter: 'Автоматизация', nav: { title: 'От сигналов — к выполненной работе', body: 'Карты, отзывы, соцсети и новости показывают владельцу, что требует внимания. Агенты забирают повторяющиеся шаги.' }, signals: { title: 'Все сигналы сходятся в LocalOS', body: 'LocalOS собирает изменения из карт, отзывов, социальных каналов и новостей и превращает их в понятные задачи.' }, today: { title: 'Результат виден за сегодня', body: 'Сводка показывает выполненные запуски, подготовленные материалы, решения владельца и ошибки.' }, employees: { title: 'Каждый агент отвечает за свою работу', body: 'Выберите цифрового сотрудника: видно, что он делает, когда запускается и какой результат подготовил.' }, control: { title: 'Автоматизация остаётся управляемой', body: 'Агент может работать по кнопке или расписанию. Публикации, отправки и ответственные изменения ждут ручного подтверждения.' } },
  en: { chapter: 'Automation', nav: { title: 'From signals to completed work', body: 'Maps, reviews, social channels, and news show the owner what needs attention. Agents take over repeatable steps.' }, signals: { title: 'All signals meet in LocalOS', body: 'LocalOS gathers changes from maps, reviews, social channels, and news and turns them into clear tasks.' }, today: { title: 'See today’s result', body: 'The summary shows completed runs, prepared materials, owner decisions, and errors.' }, employees: { title: 'Each agent owns a job', body: 'Choose a digital employee to see what it does, when it runs, and which result it prepared.' }, control: { title: 'Automation stays controlled', body: 'Agents run on demand or on schedule. Publishing, external sends, and sensitive changes wait for manual approval.' } },
  fr: { chapter: 'Automatisation', nav: { title: 'Des signaux au travail accompli', body: 'Cartes, avis, réseaux sociaux et actualités indiquent ce qui demande l’attention. Les agents prennent les étapes répétitives.' }, signals: { title: 'Tous les signaux arrivent dans LocalOS', body: 'LocalOS transforme les changements des cartes, avis, réseaux et actualités en tâches claires.' }, today: { title: 'Le résultat du jour est visible', body: 'Le résumé montre les exécutions, les contenus préparés, les décisions et les erreurs.' }, employees: { title: 'Chaque agent a une mission', body: 'Choisissez un employé numérique pour voir son travail, son rythme et ses résultats.' }, control: { title: 'L’automatisation reste contrôlée', body: 'Les agents travaillent à la demande ou selon un calendrier. Publications et envois externes attendent une validation humaine.' } },
  es: { chapter: 'Automatización', nav: { title: 'De las señales al trabajo terminado', body: 'Mapas, reseñas, redes sociales y noticias muestran qué necesita atención. Los agentes asumen los pasos repetitivos.' }, signals: { title: 'Todas las señales llegan a LocalOS', body: 'LocalOS convierte los cambios de mapas, reseñas, redes y noticias en tareas claras.' }, today: { title: 'El resultado de hoy está visible', body: 'El resumen muestra ejecuciones, materiales preparados, decisiones y errores.' }, employees: { title: 'Cada agente tiene una función', body: 'Elige un empleado digital para ver qué hace, cuándo trabaja y qué resultado preparó.' }, control: { title: 'La automatización sigue bajo control', body: 'Los agentes trabajan bajo demanda o por horario. Publicaciones y envíos externos esperan aprobación manual.' } },
  el: { chapter: 'Αυτοματοποίηση', nav: { title: 'Από τα σήματα στην ολοκληρωμένη εργασία', body: 'Χάρτες, κριτικές, κοινωνικά δίκτυα και ειδήσεις δείχνουν τι χρειάζεται προσοχή. Οι πράκτορες αναλαμβάνουν τα επαναλαμβανόμενα βήματα.' }, signals: { title: 'Όλα τα σήματα συγκεντρώνονται στο LocalOS', body: 'Το LocalOS μετατρέπει αλλαγές από χάρτες, κριτικές, κοινωνικά δίκτυα και ειδήσεις σε σαφείς εργασίες.' }, today: { title: 'Το σημερινό αποτέλεσμα είναι ορατό', body: 'Η σύνοψη δείχνει εκτελέσεις, έτοιμα υλικά, αποφάσεις του ιδιοκτήτη και σφάλματα.' }, employees: { title: 'Κάθε πράκτορας έχει συγκεκριμένη εργασία', body: 'Επιλέξτε έναν ψηφιακό υπάλληλο για να δείτε τι κάνει, πότε εκτελείται και ποιο αποτέλεσμα ετοίμασε.' }, control: { title: 'Η αυτοματοποίηση παραμένει ελεγχόμενη', body: 'Οι πράκτορες εκτελούνται κατά απαίτηση ή με πρόγραμμα. Δημοσιεύσεις και εξωτερικές αποστολές περιμένουν χειροκίνητη έγκριση.' } },
  de: { chapter: 'Automatisierung', nav: { title: 'Von Signalen zu erledigter Arbeit', body: 'Karten, Bewertungen, soziale Kanäle und Nachrichten zeigen den Handlungsbedarf. Agenten übernehmen wiederkehrende Schritte.' }, signals: { title: 'Alle Signale laufen in LocalOS zusammen', body: 'LocalOS verwandelt Änderungen aus Karten, Bewertungen, sozialen Kanälen und Nachrichten in klare Aufgaben.' }, today: { title: 'Das heutige Ergebnis ist sichtbar', body: 'Die Übersicht zeigt Läufe, vorbereitete Inhalte, Entscheidungen und Fehler.' }, employees: { title: 'Jeder Agent hat eine Aufgabe', body: 'Wählen Sie einen digitalen Mitarbeiter und sehen Sie Arbeit, Zeitplan und Ergebnis.' }, control: { title: 'Automatisierung bleibt kontrolliert', body: 'Agenten arbeiten auf Abruf oder nach Zeitplan. Veröffentlichungen und externe Sendungen warten auf manuelle Freigabe.' } },
  th: { chapter: 'ระบบอัตโนมัติ', nav: { title: 'จากสัญญาณสู่งานที่เสร็จ', body: 'แผนที่ รีวิว โซเชียล และข่าวบอกสิ่งที่ต้องดูแล เอเจนต์รับช่วงขั้นตอนที่ทำซ้ำ' }, signals: { title: 'สัญญาณทั้งหมดมารวมที่ LocalOS', body: 'LocalOS เปลี่ยนข้อมูลจากแผนที่ รีวิว โซเชียล และข่าวให้เป็นงานที่ชัดเจน' }, today: { title: 'เห็นผลลัพธ์ของวันนี้', body: 'สรุปแสดงงานที่เสร็จ เนื้อหาที่เตรียมไว้ การตัดสินใจ และข้อผิดพลาด' }, employees: { title: 'เอเจนต์แต่ละตัวมีหน้าที่', body: 'เลือกพนักงานดิจิทัลเพื่อดูหน้าที่ เวลาเริ่มงาน และผลลัพธ์' }, control: { title: 'ระบบอัตโนมัติยังอยู่ในการควบคุม', body: 'เอเจนต์ทำงานตามคำสั่งหรือตารางเวลา การเผยแพร่และส่งภายนอกยังรอการอนุมัติจากคน' } },
  ar: { chapter: 'الأتمتة', nav: { title: 'من الإشارات إلى العمل المنجز', body: 'توضح الخرائط والمراجعات والشبكات الاجتماعية والأخبار ما يحتاج إلى الاهتمام، ويتولى الوكلاء الخطوات المتكررة.' }, signals: { title: 'تجتمع كل الإشارات في LocalOS', body: 'يحوّل LocalOS تغييرات الخرائط والمراجعات والشبكات والأخبار إلى مهام واضحة.' }, today: { title: 'نتيجة اليوم واضحة', body: 'يعرض الملخص التشغيلات والمواد الجاهزة والقرارات والأخطاء.' }, employees: { title: 'لكل وكيل مهمة', body: 'اختر موظفًا رقميًا لترى عمله وموعد تشغيله والنتيجة التي أعدها.' }, control: { title: 'تبقى الأتمتة تحت السيطرة', body: 'يعمل الوكلاء عند الطلب أو وفق جدول. ينتظر النشر والإرسال الخارجي موافقة يدوية.' } },
  ha: { chapter: 'Automation', nav: { title: 'Daga alamomi zuwa aikin da aka kammala', body: 'Taswira, sharhi, kafofin sada zumunta da labarai suna nuna abin da ke bukatar kulawa. Wakilai su ɗauki ayyukan maimaitawa.' }, signals: { title: 'Duk alamomi suna haɗuwa a LocalOS', body: 'LocalOS yana juya sauye-sauyen taswira, sharhi, kafofin sada zumunta da labarai zuwa ayyuka masu bayyani.' }, today: { title: 'Ana ganin sakamakon yau', body: 'Taƙaitaccen bayani yana nuna ayyukan da aka gama, kayan da aka shirya, yanke shawara da kurakurai.' }, employees: { title: 'Kowane wakili yana da aikinsa', body: 'Zaɓi ma’aikacin dijital don ganin aikinsa, lokacin gudu da sakamakon da ya shirya.' }, control: { title: 'Automation yana ƙarƙashin kulawa', body: 'Wakilai suna aiki bisa buƙata ko jadawali. Wallafawa da aikawa waje suna jiran amincewar mutum.' } },
  tr: { chapter: 'Otomasyon', nav: { title: 'Sinyallerden tamamlanan işe', body: 'Haritalar, yorumlar, sosyal kanallar ve haberler neyin dikkat istediğini gösterir. Ajanlar tekrarlanan adımları üstlenir.' }, signals: { title: 'Tüm sinyaller LocalOS’ta birleşir', body: 'LocalOS harita, yorum, sosyal kanal ve haber değişikliklerini anlaşılır görevlere dönüştürür.' }, today: { title: 'Bugünün sonucu görünür', body: 'Özet; tamamlanan çalışmaları, hazırlanan içerikleri, kararları ve hataları gösterir.' }, employees: { title: 'Her ajanın bir işi vardır', body: 'Ne yaptığını, ne zaman çalıştığını ve hangi sonucu hazırladığını görmek için dijital çalışanı seçin.' }, control: { title: 'Otomasyon kontrol altında kalır', body: 'Ajanlar isteğe göre veya zamanlamayla çalışır. Yayınlama ve dış gönderimler manuel onay bekler.' } },
};

export const guidedTourCopyForLanguage = (language: Language): GuidedTourCopy => {
  const base = copyByLanguage[language];
  const automation = automationCopy[language];
  return {
    ...base,
    chapters: { ...base.chapters, automation: automation.chapter },
    steps: { ...base.steps, 'agents-nav': automation.nav, 'agents-signals': automation.signals, 'agents-today': automation.today, 'agents-employees': automation.employees, 'agents-control': automation.control },
  };
};

export const fillGuidedTourTemplate = (template: string, values: Record<string, string | number>) => (
  Object.entries(values).reduce((result, [key, value]) => result.replace(`{${key}}`, String(value)), template)
);
