export type CardOverviewPageCopy = {
  title: string;
  refresh: string;
  refreshing: string;
  refreshAll: string;
  refreshHint: string;
  refreshAllHint: string;
  auditTitle: string;
  rating: string;
  reviews: string;
  lastRefresh: string;
  mapSources: string;
  now: string;
  supportedSources: string;
  collapse: string;
  expand: string;
  allMaps: string;
  yandex: string;
  servicesTab: string;
  reviewsTab: string;
  newsTab: string;
  keywordsTab: string;
  competitorsTab: string;
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
  parseAlreadyRunning: string;
  parseInProgress: string;
  parseQueued: string;
  parseDone: string;
  parseError: string;
  parseIdle: string;
  nextRefresh: string;
};

const en: CardOverviewPageCopy = {
  title: 'Maps management',
  refresh: 'Refresh selected listing', refreshing: 'Starting refresh...', refreshAll: 'Refresh all listings', refreshHint: 'About 10 credits, depending on data volume.', refreshAllHint: 'About 10 credits, depending on data volume.', auditTitle: 'Opens the listing audit, metrics, and change history.',
  rating: 'Rating', reviews: 'Reviews', lastRefresh: 'Updated', mapSources: 'Platform',
  now: 'Now:', supportedSources: 'Refresh is currently supported for Yandex, 2GIS, and Google.', collapse: 'Collapse', expand: 'Expand', allMaps: 'All maps', yandex: 'Yandex', servicesTab: 'Services', reviewsTab: 'Reviews', newsTab: 'News', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Competitors',
  processProblematic: 'Process weak services', processingProblematic: 'Processing...', processProblematicHint: 'Finds services with weak or missing descriptions and improves up to 10 of the weakest in one run.', findQueries: 'Find queries', findingQueries: 'Searching...', findQueriesHint: 'Finds SEO queries for services that do not have them using a safe Wordstat search.', optimizing: 'Optimizing...', optimizeAllHint: 'Generates SEO names and descriptions for all services. Use carefully for large lists.', compressMenu: 'Simplify service menu', compressMenuHint: 'Shows which services can be combined into categories and variants. Nothing changes automatically.', addServiceHint: 'Add a service manually when it is missing from the listing data or needs a separate wording review.', settings: 'Settings', settingsHint: 'Opens tone, language, region, file import, and additional generation options.', listingUpdated: 'Listing last updated:',
  total: 'Total', ready: 'Ready', needsReview: 'Needs improvement', manualReview: 'Manual review', noQueries: 'No queries', source: 'Source', emptyFiltered: 'Nothing found for the selected filters', edit: 'Edit', automationLocked: 'Automation is available with a paid plan.',
  parseAlreadyRunning: 'Data collection is already running', parseInProgress: 'Data collection in progress', parseQueued: 'Data collection is queued', parseDone: 'Card data updated', parseError: 'Could not update card data', parseIdle: 'Card data has not been collected yet', nextRefresh: 'Next refresh will be available on {date}',
};

const hy: CardOverviewPageCopy = {
  title: "Քարտեզների կառավարում",
  refresh: "Թարմացրեք ցանկի տվյալները", refreshing: "Սկսվում է թարմացում...", refreshAll: "Թարմացրեք քարտի տվյալները", refreshHint: "Թարմացնում է միայն ընտրված քարտեզի ցանկը: Արժեքը մոտ 10 վարկ՝ կախված ցուցակման տվյալների քանակից:", refreshAllHint: "Թարմացնում է բոլոր ավելացված քարտեզների ցանկերը: Արժեքը մոտ 10 վարկ՝ կախված ցուցակման տվյալների քանակից:", auditTitle: "Բացում է ցուցակման աուդիտը, չափումները և փոփոխությունների պատմությունը:",
  rating: "Վարկանիշ", reviews: "Կարծիքներ", lastRefresh: "Վերջին թարմացում", mapSources: "Քարտեզի աղբյուրներ",
  now: "Այժմ՝", supportedSources: "Թարմացումը ներկայումս աջակցվում է Yandex-ի, 2GIS-ի և Google-ի համար:", collapse: "Փլուզում", expand: "Ընդարձակել", allMaps: "Բոլոր քարտեզները", yandex: "Յանդեքս", servicesTab: "Ծառայություններ", reviewsTab: "Կարծիքներ", newsTab: "Նորություններ", keywordsTab: 'SEO (Wordstat)', competitorsTab: "Մրցակիցներ",
  processProblematic: "Գործընթացի թույլ ծառայություններ", processingProblematic: "Մշակվում է...", processProblematicHint: "Գտնում է թույլ կամ բացակայող նկարագրություններով ծառայություններ և բարելավում է մինչև 10 ամենաթույլը մեկ գործարկման ընթացքում:", findQueries: "Գտեք հարցումներ", findingQueries: "Որոնում...", findQueriesHint: "Գտնում է SEO հարցումներ ծառայությունների համար, որոնք չունեն դրանք՝ օգտագործելով անվտանգ Wordstat որոնում:", optimizing: "Օպտիմալացում...", optimizeAllHint: "Ստեղծում է SEO անուններ և նկարագրություններ բոլոր ծառայությունների համար: Զգուշորեն օգտագործեք մեծ ցուցակների համար:", compressMenu: "Պարզեցրեք ծառայության ընտրացանկը", compressMenuHint: "Ցույց է տալիս, թե որ ծառայությունները կարող են համակցվել կատեգորիաների և տարբերակների: Ոչինչ ինքնաբերաբար չի փոխվում:", addServiceHint: "Ձեռքով ավելացրեք ծառայություն, երբ այն բացակայում է ցանկի տվյալներից կամ կարիք ունի առանձին ձևակերպումների վերանայման:", settings: "Կարգավորումներ", settingsHint: "Բացում է հնչերանգը, լեզուն, տարածաշրջանը, ֆայլերի ներմուծումը և ստեղծման լրացուցիչ ընտրանքները:", listingUpdated: "Ցուցակը վերջին անգամ թարմացվել է.",
  total: "Ընդամենը", ready: "Պատրաստ", needsReview: "Բարելավման կարիք ունի", manualReview: "Ձեռնարկի վերանայում", noQueries: "Հարցումներ չկան", source: "Աղբյուր", emptyFiltered: "Ընտրված զտիչների համար ոչինչ չի գտնվել", edit: "Խմբագրել", automationLocked: "Ավտոմատացումը հասանելի է վճարովի պլանով:",
  parseAlreadyRunning: "Տվյալների հավաքագրումն արդեն աշխատում է", parseInProgress: "Տվյալների հավաքագրումն ընթացքի մեջ է", parseQueued: "Տվյալների հավաքագրումը հերթագրված է", parseDone: "Քարտի տվյալները թարմացվել են", parseError: "Չհաջողվեց թարմացնել քարտի տվյալները", parseIdle: "Քարտի տվյալները դեռ չեն հավաքվել", nextRefresh: "Հաջորդ թարմացումը հասանելի կլինի {date}-ին",
};
const kk: CardOverviewPageCopy = {
  ...en,
  title: "Карталарды басқару",
  refresh: "Карта мәліметтерін жаңартыңыз", refreshing: "Біз жаңартуды іске қосамыз...", refreshAll: "Карта мәліметтерін жаңартыңыз", refreshHint: "Тек таңдалған карта жаңартылады. Картадағы деректер көлеміне байланысты шамамен 10 кредитті құрайды.", refreshAllHint: "Барлық қосылған карталар жаңартылады. Карталардағы деректер көлеміне байланысты шамамен 10 кредитті құрайды.", auditTitle: "Карта аудитін, көрсеткіштерді және өзгерту тарихын ашады.",
  rating: "Рейтинг", reviews: "Пікірлер", lastRefresh: "Соңғы жаңарту", mapSources: "Карта көздері", now: "Қазір:", supportedSources: "Жаңарту енді Яндекс, 2GIS және Google үшін қолдау көрсетеді.", collapse: "Жыйрату", expand: "Кеңейту", allMaps: "Барлық карталар", yandex: "Яндекс", keywordsTab: 'SEO (Wordstat)', competitorsTab: "Бәсекелестер",
  processProblematic: "Процесс мәселесі", processingProblematic: "Өңдеуде...", processProblematicHint: "Сипаттамалары әлсіз немесе бос қызметтерді тауып, бір орында ең проблемалы 10-ға дейін жақсартады.", findQueries: "Сұраныстарды табыңыз", findingQueries: "Іздеуде...", findQueriesHint: "Ол қауіпсіз Wordstat іздеуі арқылы жоқ қызметтер үшін SEO сұрауларын таңдайды.", optimizing: "Оңтайландырайық...", optimizeAllHint: "Барлық қызметтер үшін SEO тақырыптары мен сипаттамаларын жасайды. Тізім үлкен болса, мұқият пайдаланыңыз.", compressMenu: "Қызметтер мәзірін қысқарту", compressMenuHint: "Ол санаттар мен опцияларға қай қызметтердің жақсы біріктірілгенін көрсетеді. Ештеңе автоматты түрде өзгермейді.", addServiceHint: "Қызмет карта деректерінде болмаса немесе бөлек сөзді тексеру қажет болса, оны қолмен қосыңыз.", settings: "Параметрлер", settingsHint: "Тонды, тілді, аймақты, файлды импорттауды және қосымша жасау опцияларын ашады.", listingUpdated: "Картаның соңғы жаңартуы:", total: "Барлығы", ready: "Дайын", needsReview: "Жақсартуды қажет етеді", manualReview: "Қолмен тексеру", noQueries: "Сұраныс жоқ", source: "Дереккөз", emptyFiltered: "Таңдалған сүзгілер үшін ештеңе табылмады", edit: "Өңдеу", automationLocked: "Автоматтандыру тарифті төлегеннен кейін ғана қолжетімді.",
};

const ru: CardOverviewPageCopy = {
  ...en,
  title: 'Управление картами',
  refresh: 'Обновить выбранную карту', refreshing: 'Запускаем обновление...', refreshAll: 'Обновить все карты', refreshHint: 'Около 10 кредитов, зависит от объёма данных.', refreshAllHint: 'Около 10 кредитов, зависит от объёма данных.', auditTitle: 'Открывает аудит карточки, метрики и историю изменений.',
  rating: 'Рейтинг', reviews: 'Отзывы', lastRefresh: 'Обновлено', mapSources: 'Площадка', now: 'Сейчас:', supportedSources: 'Обновление сейчас поддержано для Яндекс, 2ГИС и Google.', collapse: 'Свернуть', expand: 'Развернуть', allMaps: 'Все карты', yandex: 'Яндекс', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Конкуренты',
  processProblematic: 'Обработать проблемные', processingProblematic: 'Обрабатываем...', processProblematicHint: 'Найдёт услуги со слабыми или пустыми описаниями и улучшит до 10 самых проблемных за один запуск.', findQueries: 'Найти запросы', findingQueries: 'Ищем...', findQueriesHint: 'Подберёт SEO-запросы для услуг, где их нет, через безопасный Wordstat-поиск.', optimizing: 'Оптимизируем...', optimizeAllHint: 'Сгенерирует SEO-названия и описания для всех услуг. Используйте осторожно, если список большой.', compressMenu: 'Сократить меню услуг', compressMenuHint: 'Покажет, какие услуги лучше объединить в категории и варианты. Ничего не меняет автоматически.', addServiceHint: 'Добавить услугу вручную, если её нет в данных карточки или нужно проверить отдельную формулировку.', settings: 'Настройки', settingsHint: 'Открывает тон, язык, регион, импорт файла и дополнительные параметры генерации.', listingUpdated: 'Последнее обновление карточки:', total: 'Всего', ready: 'Готово', needsReview: 'Требуют доработки', manualReview: 'Ручная проверка', noQueries: 'Без запросов', source: 'Источник', emptyFiltered: 'Ничего не найдено по выбранным фильтрам', edit: 'Редактировать', automationLocked: 'Автоматизация доступна только после оплаты тарифа.',
};

const el: CardOverviewPageCopy = {
  ...en,
  title: 'Διαχείριση χαρτών',
  refresh: 'Ενημέρωση δεδομένων καταχώρισης', refreshing: 'Έναρξη ενημέρωσης...', refreshAll: 'Ενημέρωση όλων των καταχωρίσεων', refreshHint: 'Ενημερώνεται μόνο η επιλεγμένη καταχώριση. Κοστίζει περίπου 10 πιστώσεις, ανάλογα με τον όγκο των δεδομένων.', refreshAllHint: 'Ενημερώνονται όλες οι καταχωρίσεις. Κοστίζει περίπου 10 πιστώσεις, ανάλογα με τον όγκο των δεδομένων.', auditTitle: 'Ανοίγει τον έλεγχο της καταχώρισης, τις μετρήσεις και το ιστορικό αλλαγών.',
  rating: 'Βαθμολογία', reviews: 'Κριτικές', lastRefresh: 'Τελευταία ενημέρωση', mapSources: 'Πηγές χαρτών', now: 'Τώρα:', supportedSources: 'Η ενημέρωση υποστηρίζεται για Yandex, 2GIS και Google.', collapse: 'Σύμπτυξη', expand: 'Ανάπτυξη', allMaps: 'Όλοι οι χάρτες', yandex: 'Yandex', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Ανταγωνιστές',
  processProblematic: 'Βελτίωση προβληματικών', processingProblematic: 'Επεξεργασία...', processProblematicHint: 'Εντοπίζει υπηρεσίες με αδύναμες ή κενές περιγραφές και βελτιώνει έως 10 σε κάθε εκτέλεση.', findQueries: 'Εύρεση αναζητήσεων', findingQueries: 'Αναζήτηση...', findQueriesHint: 'Βρίσκει ασφαλώς αναζητήσεις SEO μέσω Wordstat για υπηρεσίες χωρίς λέξεις-κλειδιά.', optimizing: 'Βελτιστοποίηση...', optimizeAllHint: 'Δημιουργεί τίτλους και περιγραφές SEO για όλες τις υπηρεσίες. Χρησιμοποιήστε το προσεκτικά σε μεγάλες λίστες.', compressMenu: 'Απλοποίηση μενού υπηρεσιών', compressMenuHint: 'Δείχνει ποιες υπηρεσίες μπορούν να ενωθούν σε κατηγορίες και παραλλαγές. Δεν αλλάζει τίποτα αυτόματα.', addServiceHint: 'Προσθέστε χειροκίνητα μια υπηρεσία όταν λείπει από τα δεδομένα ή χρειάζεται ξεχωριστό έλεγχο.', settings: 'Ρυθμίσεις', settingsHint: 'Ανοίγει τον τόνο, τη γλώσσα, την περιοχή, την εισαγωγή αρχείου και πρόσθετες επιλογές δημιουργίας.', listingUpdated: 'Τελευταία ενημέρωση καταχώρισης:', total: 'Σύνολο', ready: 'Έτοιμα', needsReview: 'Χρειάζονται βελτίωση', manualReview: 'Χειροκίνητος έλεγχος', noQueries: 'Χωρίς αναζητήσεις', source: 'Πηγή', emptyFiltered: 'Δεν βρέθηκαν αποτελέσματα με τα επιλεγμένα φίλτρα', edit: 'Επεξεργασία', automationLocked: 'Η αυτοματοποίηση είναι διαθέσιμη με συνδρομή επί πληρωμή.',
};

const fr: CardOverviewPageCopy = { ...en, title: 'Gestion des cartes', refresh: 'Actualiser la fiche', refreshing: 'Actualisation...', refreshAll: 'Actualiser les fiches', rating: 'Note', reviews: 'Avis', lastRefresh: 'Dernière actualisation', mapSources: 'Sources cartographiques', now: 'Maintenant :', collapse: 'Réduire', expand: 'Développer', allMaps: 'Toutes les cartes', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Concurrents', total: 'Total', ready: 'Prêt', needsReview: 'À améliorer', manualReview: 'Vérification manuelle', noQueries: 'Sans requêtes', source: 'Source', edit: 'Modifier' };
const es: CardOverviewPageCopy = { ...en, title: 'Gestión de mapas', refresh: 'Actualizar ficha', refreshing: 'Actualizando...', refreshAll: 'Actualizar fichas', rating: 'Valoración', reviews: 'Reseñas', lastRefresh: 'Última actualización', mapSources: 'Fuentes de mapas', now: 'Ahora:', collapse: 'Contraer', expand: 'Ampliar', allMaps: 'Todos los mapas', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Competidores', total: 'Total', ready: 'Listo', needsReview: 'Necesita mejoras', manualReview: 'Revisión manual', noQueries: 'Sin consultas', source: 'Fuente', edit: 'Editar' };
const de: CardOverviewPageCopy = { ...en, title: 'Kartenverwaltung', refresh: 'Eintrag aktualisieren', refreshing: 'Aktualisierung...', refreshAll: 'Einträge aktualisieren', rating: 'Bewertung', reviews: 'Rezensionen', lastRefresh: 'Letzte Aktualisierung', mapSources: 'Kartenquellen', now: 'Jetzt:', collapse: 'Einklappen', expand: 'Ausklappen', allMaps: 'Alle Karten', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Wettbewerber', total: 'Gesamt', ready: 'Bereit', needsReview: 'Verbesserung nötig', manualReview: 'Manuelle Prüfung', noQueries: 'Ohne Suchbegriffe', source: 'Quelle', edit: 'Bearbeiten' };
const th: CardOverviewPageCopy = { ...en, title: 'การจัดการแผนที่', refresh: 'รีเฟรชข้อมูล', refreshing: 'กำลังรีเฟรช...', refreshAll: 'รีเฟรชทุกข้อมูล', rating: 'คะแนน', reviews: 'รีวิว', lastRefresh: 'อัปเดตล่าสุด', mapSources: 'แหล่งแผนที่', now: 'ตอนนี้:', collapse: 'ย่อ', expand: 'ขยาย', allMaps: 'ทุกแผนที่', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'คู่แข่ง', total: 'ทั้งหมด', ready: 'พร้อม', needsReview: 'ต้องปรับปรุง', manualReview: 'ตรวจสอบด้วยตนเอง', noQueries: 'ไม่มีคำค้นหา', source: 'แหล่งข้อมูล', edit: 'แก้ไข' };
const ar: CardOverviewPageCopy = { ...en, title: 'إدارة الخرائط', refresh: 'تحديث القائمة', refreshing: 'جارٍ التحديث...', refreshAll: 'تحديث القوائم', rating: 'التقييم', reviews: 'المراجعات', lastRefresh: 'آخر تحديث', mapSources: 'مصادر الخرائط', now: 'الآن:', collapse: 'طي', expand: 'توسيع', allMaps: 'كل الخرائط', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'المنافسون', total: 'الإجمالي', ready: 'جاهز', needsReview: 'يحتاج تحسينًا', manualReview: 'مراجعة يدوية', noQueries: 'بلا استعلامات', source: 'المصدر', edit: 'تعديل' };
const ha: CardOverviewPageCopy = { ...en, title: 'Gudanar da taswira', refresh: 'Sabunta jeri', refreshing: 'Ana sabuntawa...', refreshAll: 'Sabunta jerin', rating: 'Maki', reviews: 'Sharhi', lastRefresh: 'Sabuntawa ta ƙarshe', mapSources: 'Tushen taswira', now: 'Yanzu:', collapse: 'Rufe', expand: 'Buɗe', allMaps: 'Duk taswirori', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Masu gasa', total: 'Duka', ready: 'A shirye', needsReview: 'Na buƙatar gyara', manualReview: 'Binciken hannu', noQueries: 'Babu tambayoyi', source: 'Tushe', edit: 'Gyara' };
const tr: CardOverviewPageCopy = { ...en, title: 'Harita Yönetimi', refresh: 'Kaydı yenile', refreshing: 'Yenileniyor...', refreshAll: 'Kayıtları yenile', refreshHint: 'Yalnızca seçili harita kaydını yeniler. Kayıt verilerinin miktarına bağlı olarak yaklaşık 10 kredi tutar.', refreshAllHint: 'Eklenen tüm harita kayıtlarını yeniler. Kayıt verilerinin miktarına bağlı olarak yaklaşık 10 kredi tutar.', auditTitle: 'Kayıt denetimini, metrikleri ve değişiklik geçmişini açar.', rating: 'Puan', reviews: 'Yorumlar', lastRefresh: 'Son yenileme', mapSources: 'Harita kaynakları', now: 'Şimdi:', supportedSources: 'Yenileme şu anda Yandex, 2GIS ve Google için destekleniyor.', collapse: 'Daralt', expand: 'Genişlet', allMaps: 'Tüm haritalar', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Rakipler', total: 'Toplam', ready: 'Hazır', needsReview: 'Geliştirilmeli', manualReview: 'Elle inceleme', noQueries: 'Sorgu yok', source: 'Kaynak', edit: 'Düzenle' };

type CardRuntimeCopy = Pick<CardOverviewPageCopy, 'servicesTab' | 'reviewsTab' | 'newsTab' | 'parseAlreadyRunning' | 'parseInProgress' | 'parseQueued' | 'parseDone' | 'parseError' | 'parseIdle' | 'nextRefresh'>;
const runtimeByLanguage: Record<string, CardRuntimeCopy> = {
  hy: { servicesTab: 'Ծառայություններ', reviewsTab: 'Կարծիքներ', newsTab: 'Նորություններ', parseAlreadyRunning: 'Տվյալների հավաքագրումն արդեն ընթացքի մեջ է', parseInProgress: 'Տվյալները հավաքագրվում են', parseQueued: 'Տվյալների հավաքագրումը հերթում է', parseDone: 'Քարտի տվյալները թարմացվել են', parseError: 'Չհաջողվեց թարմացնել քարտի տվյալները', parseIdle: 'Քարտի տվյալները դեռ չեն հավաքագրվել', nextRefresh: 'Հաջորդ թարմացումը հասանելի կլինի {date}-ին' },
  kk: { servicesTab: "Қызметтер", reviewsTab: "Пікірлер", newsTab: "Жаңалықтар", parseAlreadyRunning: "Деректер жинау қазірдің өзінде жүріп жатыр", parseInProgress: "Деректерді жинау орындалуда", parseQueued: "Кезекте деректерді жинау", parseDone: "Карта мәліметтері жаңартылды", parseError: "Деректерді жаңарту мүмкін болмады", parseIdle: "Карта деректері әлі жаңартылған жоқ", nextRefresh: "Келесі жаңарту қолжетімді {date}" },
  en: { servicesTab: 'Services', reviewsTab: 'Reviews', newsTab: 'News', parseAlreadyRunning: 'Data collection is already running', parseInProgress: 'Data collection in progress', parseQueued: 'Data collection is queued', parseDone: 'Card data updated', parseError: 'Could not update card data', parseIdle: 'Card data has not been collected yet', nextRefresh: 'Next refresh will be available on {date}' },
  ru: { servicesTab: 'Услуги', reviewsTab: 'Отзывы', newsTab: 'Новости', parseAlreadyRunning: 'Сбор данных уже выполняется', parseInProgress: 'Сбор данных выполняется', parseQueued: 'Сбор данных в очереди', parseDone: 'Данные карточки обновлены', parseError: 'Не удалось обновить данные', parseIdle: 'Данные карточки ещё не обновлялись', nextRefresh: 'Следующее обновление доступно {date}' },
  fr: { servicesTab: 'Services', reviewsTab: 'Avis', newsTab: 'Actualités', parseAlreadyRunning: 'La collecte est déjà en cours', parseInProgress: 'Collecte des données en cours', parseQueued: 'Collecte des données en attente', parseDone: 'Données de la fiche actualisées', parseError: 'Impossible d’actualiser les données', parseIdle: 'Les données n’ont pas encore été collectées', nextRefresh: 'Prochaine actualisation disponible le {date}' },
  es: { servicesTab: 'Servicios', reviewsTab: 'Reseñas', newsTab: 'Noticias', parseAlreadyRunning: 'La recopilación ya está en curso', parseInProgress: 'Recopilando datos', parseQueued: 'Recopilación en cola', parseDone: 'Datos de la ficha actualizados', parseError: 'No se pudieron actualizar los datos', parseIdle: 'Los datos aún no se han recopilado', nextRefresh: 'Próxima actualización disponible el {date}' },
  el: { servicesTab: 'Υπηρεσίες', reviewsTab: 'Κριτικές', newsTab: 'Νέα', parseAlreadyRunning: 'Η συλλογή δεδομένων εκτελείται ήδη', parseInProgress: 'Η συλλογή δεδομένων βρίσκεται σε εξέλιξη', parseQueued: 'Η συλλογή δεδομένων βρίσκεται στην ουρά', parseDone: 'Τα δεδομένα της καταχώρισης ενημερώθηκαν', parseError: 'Δεν ήταν δυνατή η ενημέρωση των δεδομένων της καταχώρισης', parseIdle: 'Τα δεδομένα δεν έχουν συλλεχθεί ακόμη', nextRefresh: 'Η επόμενη ενημέρωση θα είναι διαθέσιμη στις {date}' },
  de: { servicesTab: 'Leistungen', reviewsTab: 'Rezensionen', newsTab: 'Neuigkeiten', parseAlreadyRunning: 'Datenerfassung läuft bereits', parseInProgress: 'Daten werden erfasst', parseQueued: 'Datenerfassung ist eingeplant', parseDone: 'Kartendaten aktualisiert', parseError: 'Kartendaten konnten nicht aktualisiert werden', parseIdle: 'Kartendaten wurden noch nicht erfasst', nextRefresh: 'Nächste Aktualisierung verfügbar am {date}' },
  th: { servicesTab: 'บริการ', reviewsTab: 'รีวิว', newsTab: 'ข่าว', parseAlreadyRunning: 'กำลังเก็บข้อมูลอยู่แล้ว', parseInProgress: 'กำลังเก็บข้อมูล', parseQueued: 'การเก็บข้อมูลอยู่ในคิว', parseDone: 'อัปเดตข้อมูลแล้ว', parseError: 'อัปเดตข้อมูลไม่ได้', parseIdle: 'ยังไม่ได้เก็บข้อมูล', nextRefresh: 'รีเฟรชครั้งถัดไปได้ใน {date}' },
  ar: { servicesTab: 'الخدمات', reviewsTab: 'المراجعات', newsTab: 'الأخبار', parseAlreadyRunning: 'جمع البيانات قيد التشغيل بالفعل', parseInProgress: 'جارٍ جمع البيانات', parseQueued: 'جمع البيانات في قائمة الانتظار', parseDone: 'تم تحديث بيانات القائمة', parseError: 'تعذر تحديث بيانات القائمة', parseIdle: 'لم تُجمع البيانات بعد', nextRefresh: 'يتاح التحديث التالي في {date}' },
  ha: { servicesTab: 'Ayyuka', reviewsTab: 'Sharhi', newsTab: 'Labarai', parseAlreadyRunning: 'Ana tattara bayanai yanzu', parseInProgress: 'Ana tattara bayanai', parseQueued: 'An saka tattara bayanai a layi', parseDone: 'An sabunta bayanan jeri', parseError: 'Ba a iya sabunta bayanan jeri ba', parseIdle: 'Ba a tattara bayanai ba tukuna', nextRefresh: 'Sabuntawa na gaba zai samu a {date}' },
  tr: { servicesTab: 'Hizmetler', reviewsTab: 'Yorumlar', newsTab: 'Haberler', parseAlreadyRunning: 'Veri toplama zaten çalışıyor', parseInProgress: 'Veriler toplanıyor', parseQueued: 'Veri toplama sırada', parseDone: 'Kayıt verileri güncellendi', parseError: 'Kayıt verileri güncellenemedi', parseIdle: 'Kayıt verileri henüz toplanmadı', nextRefresh: 'Sonraki yenileme {date} tarihinde kullanılabilir' },
};

export const getCardOverviewPageCopy = (language: string): CardOverviewPageCopy => {
  const localized = language === 'kk' ? kk : language === 'hy' ? hy : language === 'ru' ? ru : language === 'el' ? el : language === 'fr' ? fr : language === 'es' ? es : language === 'de' ? de : language === 'th' ? th : language === 'ar' ? ar : language === 'ha' ? ha : language === 'tr' ? tr : en;
  return { ...localized, ...(runtimeByLanguage[language] || runtimeByLanguage.en) };
};
