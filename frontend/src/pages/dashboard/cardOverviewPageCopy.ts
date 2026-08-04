export type CardOverviewPageCopy = {
  eyebrow: string;
  title: string;
  subtitle: string;
  refresh: string;
  refreshing: string;
  refreshAll: string;
  refreshHint: string;
  refreshAllHint: string;
  refreshTitle: string;
  auditTitle: string;
  rating: string;
  ratingHint: string;
  reviews: string;
  reviewsHint: string;
  lastRefresh: string;
  lastRefreshHint: string;
  mapSources: string;
  mapSourcesHint: string;
  now: string;
  supportedSources: string;
  collapse: string;
  expand: string;
  allMaps: string;
  yandex: string;
  keywordsTab: string;
  competitorsTab: string;
  ratingDescription: string;
  servicesTitle: string;
  servicesDescription: string;
  processProblematic: string;
  processingProblematic: string;
  processProblematicHint: string;
  findQueries: string;
  findingQueries: string;
  findQueriesHint: string;
  optimizing: string;
  optimizeAllHint: string;
  compressMenu: string;
  compressMenuHint: string;
  addServiceHint: string;
  settings: string;
  settingsHint: string;
  listingUpdated: string;
  total: string;
  ready: string;
  needsReview: string;
  manualReview: string;
  noQueries: string;
  source: string;
  emptyFiltered: string;
  edit: string;
  automationLocked: string;
};

const en: CardOverviewPageCopy = {
  eyebrow: 'Business listing', title: 'Maps management', subtitle: 'Manage listing data, services, reviews, news, search visibility, and competitors in one place.',
  refresh: 'Refresh listing data', refreshing: 'Starting refresh...', refreshAll: 'Refresh card data', refreshHint: 'Refreshes only the selected map listing. Costs about 10 credits, depending on the amount of listing data.', refreshAllHint: 'Refreshes all added map listings. Costs about 10 credits, depending on the amount of listing data.', refreshTitle: 'Starts collecting fresh data from your map listing.', auditTitle: 'Opens the listing audit, metrics, and change history.',
  rating: 'Rating', ratingHint: 'Average map listing rating.', reviews: 'Reviews', reviewsHint: 'Current review volume in the listing.', lastRefresh: 'Last refresh', lastRefreshHint: 'When the section data was last refreshed.', mapSources: 'Map sources', mapSourcesHint: 'Connected map profiles for this location.',
  now: 'Now:', supportedSources: 'Refresh is currently supported for Yandex, 2GIS, and Google.', collapse: 'Collapse', expand: 'Expand', allMaps: 'All maps', yandex: 'Yandex', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Competitors', ratingDescription: 'A short summary of the listing rating and reviews.',
  servicesTitle: 'Services', servicesDescription: 'Check how services will appear in map listings and search. Improve weak descriptions and review prepared SEO suggestions.', processProblematic: 'Process weak services', processingProblematic: 'Processing...', processProblematicHint: 'Finds services with weak or missing descriptions and improves up to 10 of the weakest in one run.', findQueries: 'Find queries', findingQueries: 'Searching...', findQueriesHint: 'Finds SEO queries for services that do not have them using a safe Wordstat search.', optimizing: 'Optimizing...', optimizeAllHint: 'Generates SEO names and descriptions for all services. Use carefully for large lists.', compressMenu: 'Simplify service menu', compressMenuHint: 'Shows which services can be combined into categories and variants. Nothing changes automatically.', addServiceHint: 'Add a service manually when it is missing from the listing data or needs a separate wording review.', settings: 'Settings', settingsHint: 'Opens tone, language, region, file import, and additional generation options.', listingUpdated: 'Listing last updated:',
  total: 'Total', ready: 'Ready', needsReview: 'Needs improvement', manualReview: 'Manual review', noQueries: 'No queries', source: 'Source', emptyFiltered: 'Nothing found for the selected filters', edit: 'Edit', automationLocked: 'Automation is available with a paid plan.',
};

const ru: CardOverviewPageCopy = {
  ...en,
  eyebrow: 'Карточка бизнеса', title: 'Управление картами', subtitle: 'Управляйте данными карточки, услугами, отзывами, новостями, видимостью в поиске и конкурентами.',
  refresh: 'Обновить данные карточки', refreshing: 'Запускаем обновление...', refreshAll: 'Обновить данные карточек', refreshHint: 'Обновится только выбранная карта. Стоит примерно 10 кредитов, зависит от объёма данных в карточке.', refreshAllHint: 'Обновятся все добавленные карты. Стоит примерно 10 кредитов, зависит от объёма данных в карточках.', refreshTitle: 'Запускает сбор свежих данных по вашей карточке на карте.', auditTitle: 'Открывает аудит карточки, метрики и историю изменений.',
  rating: 'Рейтинг', ratingHint: 'Средняя оценка карточки на карте.', reviews: 'Отзывы', reviewsHint: 'Текущий объём отзывов в карточке.', lastRefresh: 'Последнее обновление', lastRefreshHint: 'Когда данные в разделе обновлялись в последний раз.', mapSources: 'Источники карт', mapSourcesHint: 'Подключённые карточки для этой точки.', now: 'Сейчас:', supportedSources: 'Обновление сейчас поддержано для Яндекс, 2ГИС и Google.', collapse: 'Свернуть', expand: 'Развернуть', allMaps: 'Все карты', yandex: 'Яндекс', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Конкуренты', ratingDescription: 'Короткая сводка по рейтингу и отзывам карточки.',
  servicesTitle: 'Услуги', servicesDescription: 'Проверьте, как услуги будут выглядеть в карточках и поиске. Закройте слабые описания и примите готовые SEO-варианты.', processProblematic: 'Обработать проблемные', processingProblematic: 'Обрабатываем...', processProblematicHint: 'Найдёт услуги со слабыми или пустыми описаниями и улучшит до 10 самых проблемных за один запуск.', findQueries: 'Найти запросы', findingQueries: 'Ищем...', findQueriesHint: 'Подберёт SEO-запросы для услуг, где их нет, через безопасный Wordstat-поиск.', optimizing: 'Оптимизируем...', optimizeAllHint: 'Сгенерирует SEO-названия и описания для всех услуг. Используйте осторожно, если список большой.', compressMenu: 'Сократить меню услуг', compressMenuHint: 'Покажет, какие услуги лучше объединить в категории и варианты. Ничего не меняет автоматически.', addServiceHint: 'Добавить услугу вручную, если её нет в данных карточки или нужно проверить отдельную формулировку.', settings: 'Настройки', settingsHint: 'Открывает тон, язык, регион, импорт файла и дополнительные параметры генерации.', listingUpdated: 'Последнее обновление карточки:', total: 'Всего', ready: 'Готово', needsReview: 'Требуют доработки', manualReview: 'Ручная проверка', noQueries: 'Без запросов', source: 'Источник', emptyFiltered: 'Ничего не найдено по выбранным фильтрам', edit: 'Редактировать', automationLocked: 'Автоматизация доступна только после оплаты тарифа.',
};

const el: CardOverviewPageCopy = {
  ...en,
  eyebrow: 'ΚΑΡΤΑ ΕΠΙΧΕΙΡΗΣΗΣ', title: 'Διαχείριση χαρτών', subtitle: 'Διαχειριστείτε τα δεδομένα της καταχώρισης, τις υπηρεσίες, τις κριτικές, τα νέα, την προβολή στην αναζήτηση και τους ανταγωνιστές.',
  refresh: 'Ενημέρωση δεδομένων καταχώρισης', refreshing: 'Έναρξη ενημέρωσης...', refreshAll: 'Ενημέρωση όλων των καταχωρίσεων', refreshHint: 'Ενημερώνεται μόνο η επιλεγμένη καταχώριση. Κοστίζει περίπου 10 πιστώσεις, ανάλογα με τον όγκο των δεδομένων.', refreshAllHint: 'Ενημερώνονται όλες οι καταχωρίσεις. Κοστίζει περίπου 10 πιστώσεις, ανάλογα με τον όγκο των δεδομένων.', refreshTitle: 'Ξεκινά τη συλλογή πρόσφατων δεδομένων από την καταχώριση στον χάρτη.', auditTitle: 'Ανοίγει τον έλεγχο της καταχώρισης, τις μετρήσεις και το ιστορικό αλλαγών.',
  rating: 'Βαθμολογία', ratingHint: 'Μέση βαθμολογία της καταχώρισης στον χάρτη.', reviews: 'Κριτικές', reviewsHint: 'Τρέχων αριθμός κριτικών στην καταχώριση.', lastRefresh: 'Τελευταία ενημέρωση', lastRefreshHint: 'Πότε ενημερώθηκαν τελευταία τα δεδομένα αυτής της ενότητας.', mapSources: 'Πηγές χαρτών', mapSourcesHint: 'Συνδεδεμένες καταχωρίσεις χαρτών για αυτή την τοποθεσία.', now: 'Τώρα:', supportedSources: 'Η ενημέρωση υποστηρίζεται για Yandex, 2GIS και Google.', collapse: 'Σύμπτυξη', expand: 'Ανάπτυξη', allMaps: 'Όλοι οι χάρτες', yandex: 'Yandex', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Ανταγωνιστές', ratingDescription: 'Σύντομη σύνοψη της βαθμολογίας και των κριτικών της καταχώρισης.',
  servicesTitle: 'Υπηρεσίες', servicesDescription: 'Ελέγξτε πώς εμφανίζονται οι υπηρεσίες στους χάρτες και στην αναζήτηση. Βελτιώστε τις αδύναμες περιγραφές και ελέγξτε τις έτοιμες προτάσεις SEO.', processProblematic: 'Βελτίωση προβληματικών', processingProblematic: 'Επεξεργασία...', processProblematicHint: 'Εντοπίζει υπηρεσίες με αδύναμες ή κενές περιγραφές και βελτιώνει έως 10 σε κάθε εκτέλεση.', findQueries: 'Εύρεση αναζητήσεων', findingQueries: 'Αναζήτηση...', findQueriesHint: 'Βρίσκει ασφαλώς αναζητήσεις SEO μέσω Wordstat για υπηρεσίες χωρίς λέξεις-κλειδιά.', optimizing: 'Βελτιστοποίηση...', optimizeAllHint: 'Δημιουργεί τίτλους και περιγραφές SEO για όλες τις υπηρεσίες. Χρησιμοποιήστε το προσεκτικά σε μεγάλες λίστες.', compressMenu: 'Απλοποίηση μενού υπηρεσιών', compressMenuHint: 'Δείχνει ποιες υπηρεσίες μπορούν να ενωθούν σε κατηγορίες και παραλλαγές. Δεν αλλάζει τίποτα αυτόματα.', addServiceHint: 'Προσθέστε χειροκίνητα μια υπηρεσία όταν λείπει από τα δεδομένα ή χρειάζεται ξεχωριστό έλεγχο.', settings: 'Ρυθμίσεις', settingsHint: 'Ανοίγει τον τόνο, τη γλώσσα, την περιοχή, την εισαγωγή αρχείου και πρόσθετες επιλογές δημιουργίας.', listingUpdated: 'Τελευταία ενημέρωση καταχώρισης:', total: 'Σύνολο', ready: 'Έτοιμα', needsReview: 'Χρειάζονται βελτίωση', manualReview: 'Χειροκίνητος έλεγχος', noQueries: 'Χωρίς αναζητήσεις', source: 'Πηγή', emptyFiltered: 'Δεν βρέθηκαν αποτελέσματα με τα επιλεγμένα φίλτρα', edit: 'Επεξεργασία', automationLocked: 'Η αυτοματοποίηση είναι διαθέσιμη με συνδρομή επί πληρωμή.',
};

export const getCardOverviewPageCopy = (language: string): CardOverviewPageCopy => {
  if (language === 'ru') return ru;
  if (language === 'el') return el;
  return en;
};
