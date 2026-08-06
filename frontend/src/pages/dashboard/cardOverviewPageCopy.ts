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
  servicesTab: string;
  reviewsTab: string;
  newsTab: string;
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
  parseAlreadyRunning: string;
  parseInProgress: string;
  parseQueued: string;
  parseDone: string;
  parseError: string;
  parseIdle: string;
  nextRefresh: string;
};

const en: CardOverviewPageCopy = {
  eyebrow: 'Business listing', title: 'Maps management', subtitle: 'Manage listing data, services, reviews, news, search visibility, and competitors in one place.',
  refresh: 'Refresh listing data', refreshing: 'Starting refresh...', refreshAll: 'Refresh card data', refreshHint: 'Refreshes only the selected map listing. Costs about 10 credits, depending on the amount of listing data.', refreshAllHint: 'Refreshes all added map listings. Costs about 10 credits, depending on the amount of listing data.', refreshTitle: 'Starts collecting fresh data from your map listing.', auditTitle: 'Opens the listing audit, metrics, and change history.',
  rating: 'Rating', ratingHint: 'Average map listing rating.', reviews: 'Reviews', reviewsHint: 'Current review volume in the listing.', lastRefresh: 'Last refresh', lastRefreshHint: 'When the section data was last refreshed.', mapSources: 'Map sources', mapSourcesHint: 'Connected map profiles for this location.',
  now: 'Now:', supportedSources: 'Refresh is currently supported for Yandex, 2GIS, and Google.', collapse: 'Collapse', expand: 'Expand', allMaps: 'All maps', yandex: 'Yandex', servicesTab: 'Services', reviewsTab: 'Reviews', newsTab: 'News', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Competitors', ratingDescription: 'A short summary of the listing rating and reviews.',
  servicesTitle: 'Services', servicesDescription: 'Check how services will appear in map listings and search. Improve weak descriptions and review prepared SEO suggestions.', processProblematic: 'Process weak services', processingProblematic: 'Processing...', processProblematicHint: 'Finds services with weak or missing descriptions and improves up to 10 of the weakest in one run.', findQueries: 'Find queries', findingQueries: 'Searching...', findQueriesHint: 'Finds SEO queries for services that do not have them using a safe Wordstat search.', optimizing: 'Optimizing...', optimizeAllHint: 'Generates SEO names and descriptions for all services. Use carefully for large lists.', compressMenu: 'Simplify service menu', compressMenuHint: 'Shows which services can be combined into categories and variants. Nothing changes automatically.', addServiceHint: 'Add a service manually when it is missing from the listing data or needs a separate wording review.', settings: 'Settings', settingsHint: 'Opens tone, language, region, file import, and additional generation options.', listingUpdated: 'Listing last updated:',
  total: 'Total', ready: 'Ready', needsReview: 'Needs improvement', manualReview: 'Manual review', noQueries: 'No queries', source: 'Source', emptyFiltered: 'Nothing found for the selected filters', edit: 'Edit', automationLocked: 'Automation is available with a paid plan.',
  parseAlreadyRunning: 'Data collection is already running', parseInProgress: 'Data collection in progress', parseQueued: 'Data collection is queued', parseDone: 'Card data updated', parseError: 'Could not update card data', parseIdle: 'Card data has not been collected yet', nextRefresh: 'Next refresh will be available on {date}',
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

const fr: CardOverviewPageCopy = { ...en, eyebrow: 'Fiche entreprise', title: 'Gestion des cartes', subtitle: 'Gérez les fiches, services, avis, actualités, visibilité et concurrents au même endroit.', refresh: 'Actualiser la fiche', refreshing: 'Actualisation...', refreshAll: 'Actualiser les fiches', rating: 'Note', ratingHint: 'Note moyenne de la fiche.', reviews: 'Avis', reviewsHint: 'Nombre actuel d’avis.', lastRefresh: 'Dernière actualisation', lastRefreshHint: 'Dernière mise à jour des données.', mapSources: 'Sources cartographiques', mapSourcesHint: 'Fiches connectées pour cet établissement.', now: 'Maintenant :', collapse: 'Réduire', expand: 'Développer', allMaps: 'Toutes les cartes', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Concurrents', servicesTitle: 'Services', servicesDescription: 'Vérifiez la présentation des services et améliorez les descriptions faibles.', total: 'Total', ready: 'Prêt', needsReview: 'À améliorer', manualReview: 'Vérification manuelle', noQueries: 'Sans requêtes', source: 'Source', edit: 'Modifier' };
const es: CardOverviewPageCopy = { ...en, eyebrow: 'Ficha del negocio', title: 'Gestión de mapas', subtitle: 'Gestiona fichas, servicios, reseñas, noticias, visibilidad y competidores en un solo lugar.', refresh: 'Actualizar ficha', refreshing: 'Actualizando...', refreshAll: 'Actualizar fichas', rating: 'Valoración', ratingHint: 'Valoración media de la ficha.', reviews: 'Reseñas', reviewsHint: 'Número actual de reseñas.', lastRefresh: 'Última actualización', lastRefreshHint: 'Última actualización de los datos.', mapSources: 'Fuentes de mapas', mapSourcesHint: 'Fichas conectadas para esta ubicación.', now: 'Ahora:', collapse: 'Contraer', expand: 'Ampliar', allMaps: 'Todos los mapas', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Competidores', servicesTitle: 'Servicios', servicesDescription: 'Comprueba cómo aparecen los servicios y mejora las descripciones débiles.', total: 'Total', ready: 'Listo', needsReview: 'Necesita mejoras', manualReview: 'Revisión manual', noQueries: 'Sin consultas', source: 'Fuente', edit: 'Editar' };
const de: CardOverviewPageCopy = { ...en, eyebrow: 'Unternehmenseintrag', title: 'Kartenverwaltung', subtitle: 'Verwalten Sie Einträge, Leistungen, Bewertungen, Neuigkeiten, Sichtbarkeit und Wettbewerber zentral.', refresh: 'Eintrag aktualisieren', refreshing: 'Aktualisierung...', refreshAll: 'Einträge aktualisieren', rating: 'Bewertung', ratingHint: 'Durchschnittliche Kartenbewertung.', reviews: 'Rezensionen', reviewsHint: 'Aktuelle Anzahl der Rezensionen.', lastRefresh: 'Letzte Aktualisierung', lastRefreshHint: 'Letzte Datenaktualisierung.', mapSources: 'Kartenquellen', mapSourcesHint: 'Verbundene Einträge für diesen Standort.', now: 'Jetzt:', collapse: 'Einklappen', expand: 'Ausklappen', allMaps: 'Alle Karten', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Wettbewerber', servicesTitle: 'Leistungen', servicesDescription: 'Prüfen Sie die Darstellung der Leistungen und verbessern Sie schwache Beschreibungen.', total: 'Gesamt', ready: 'Bereit', needsReview: 'Verbesserung nötig', manualReview: 'Manuelle Prüfung', noQueries: 'Ohne Suchbegriffe', source: 'Quelle', edit: 'Bearbeiten' };
const th: CardOverviewPageCopy = { ...en, eyebrow: 'ข้อมูลธุรกิจ', title: 'การจัดการแผนที่', subtitle: 'จัดการข้อมูล บริการ รีวิว ข่าว การมองเห็น และคู่แข่งในที่เดียว', refresh: 'รีเฟรชข้อมูล', refreshing: 'กำลังรีเฟรช...', refreshAll: 'รีเฟรชทุกข้อมูล', rating: 'คะแนน', ratingHint: 'คะแนนเฉลี่ยบนแผนที่', reviews: 'รีวิว', reviewsHint: 'จำนวนรีวิวปัจจุบัน', lastRefresh: 'อัปเดตล่าสุด', lastRefreshHint: 'เวลาที่อัปเดตข้อมูลล่าสุด', mapSources: 'แหล่งแผนที่', mapSourcesHint: 'ข้อมูลแผนที่ที่เชื่อมต่อ', now: 'ตอนนี้:', collapse: 'ย่อ', expand: 'ขยาย', allMaps: 'ทุกแผนที่', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'คู่แข่ง', servicesTitle: 'บริการ', servicesDescription: 'ตรวจสอบการแสดงบริการและปรับปรุงคำอธิบายที่ยังไม่ดี', total: 'ทั้งหมด', ready: 'พร้อม', needsReview: 'ต้องปรับปรุง', manualReview: 'ตรวจสอบด้วยตนเอง', noQueries: 'ไม่มีคำค้นหา', source: 'แหล่งข้อมูล', edit: 'แก้ไข' };
const ar: CardOverviewPageCopy = { ...en, eyebrow: 'ملف النشاط', title: 'إدارة الخرائط', subtitle: 'أدر القوائم والخدمات والمراجعات والأخبار والظهور والمنافسين في مكان واحد.', refresh: 'تحديث القائمة', refreshing: 'جارٍ التحديث...', refreshAll: 'تحديث القوائم', rating: 'التقييم', ratingHint: 'متوسط تقييم القائمة.', reviews: 'المراجعات', reviewsHint: 'عدد المراجعات الحالي.', lastRefresh: 'آخر تحديث', lastRefreshHint: 'آخر وقت لتحديث البيانات.', mapSources: 'مصادر الخرائط', mapSourcesHint: 'القوائم المتصلة لهذا الموقع.', now: 'الآن:', collapse: 'طي', expand: 'توسيع', allMaps: 'كل الخرائط', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'المنافسون', servicesTitle: 'الخدمات', servicesDescription: 'تحقق من عرض الخدمات وحسّن الأوصاف الضعيفة.', total: 'الإجمالي', ready: 'جاهز', needsReview: 'يحتاج تحسينًا', manualReview: 'مراجعة يدوية', noQueries: 'بلا استعلامات', source: 'المصدر', edit: 'تعديل' };
const ha: CardOverviewPageCopy = { ...en, eyebrow: 'Bayanan kasuwanci', title: 'Gudanar da taswira', subtitle: 'Gudanar da jeri, ayyuka, sharhi, labarai, bayyanar nema da masu gasa a wuri ɗaya.', refresh: 'Sabunta jeri', refreshing: 'Ana sabuntawa...', refreshAll: 'Sabunta jerin', rating: 'Maki', ratingHint: 'Matsakaicin makin jeri.', reviews: 'Sharhi', reviewsHint: 'Yawan sharhi na yanzu.', lastRefresh: 'Sabuntawa ta ƙarshe', lastRefreshHint: 'Lokacin sabunta bayanai na ƙarshe.', mapSources: 'Tushen taswira', mapSourcesHint: 'Jerin taswirar da aka haɗa.', now: 'Yanzu:', collapse: 'Rufe', expand: 'Buɗe', allMaps: 'Duk taswirori', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Masu gasa', servicesTitle: 'Ayyuka', servicesDescription: 'Duba yadda ayyuka suke bayyana kuma inganta bayanin da bai da ƙarfi.', total: 'Duka', ready: 'A shirye', needsReview: 'Na buƙatar gyara', manualReview: 'Binciken hannu', noQueries: 'Babu tambayoyi', source: 'Tushe', edit: 'Gyara' };
const tr: CardOverviewPageCopy = { ...en, eyebrow: 'İşletme kaydı', title: 'Harita Yönetimi', subtitle: 'Kayıtları, hizmetleri, yorumları, haberleri, arama görünürlüğünü ve rakipleri tek yerde yönetin.', refresh: 'Kaydı yenile', refreshing: 'Yenileniyor...', refreshAll: 'Kayıtları yenile', refreshHint: 'Yalnızca seçili harita kaydını yeniler. Kayıt verilerinin miktarına bağlı olarak yaklaşık 10 kredi tutar.', refreshAllHint: 'Eklenen tüm harita kayıtlarını yeniler. Kayıt verilerinin miktarına bağlı olarak yaklaşık 10 kredi tutar.', refreshTitle: 'Harita kaydınızdan güncel veri toplamaya başlar.', auditTitle: 'Kayıt denetimini, metrikleri ve değişiklik geçmişini açar.', rating: 'Puan', ratingHint: 'Harita kaydının ortalama puanı.', reviews: 'Yorumlar', reviewsHint: 'Güncel yorum sayısı.', lastRefresh: 'Son yenileme', lastRefreshHint: 'Verilerin son yenilenme zamanı.', mapSources: 'Harita kaynakları', mapSourcesHint: 'Bu konum için bağlı kayıtlar.', now: 'Şimdi:', supportedSources: 'Yenileme şu anda Yandex, 2GIS ve Google için destekleniyor.', collapse: 'Daralt', expand: 'Genişlet', allMaps: 'Tüm haritalar', keywordsTab: 'SEO (Wordstat)', competitorsTab: 'Rakipler', servicesTitle: 'Hizmetler', servicesDescription: 'Hizmetlerin görünümünü kontrol edin ve zayıf açıklamaları geliştirin.', total: 'Toplam', ready: 'Hazır', needsReview: 'Geliştirilmeli', manualReview: 'Elle inceleme', noQueries: 'Sorgu yok', source: 'Kaynak', edit: 'Düzenle' };

type CardRuntimeCopy = Pick<CardOverviewPageCopy, 'servicesTab' | 'reviewsTab' | 'newsTab' | 'parseAlreadyRunning' | 'parseInProgress' | 'parseQueued' | 'parseDone' | 'parseError' | 'parseIdle' | 'nextRefresh'>;
const runtimeByLanguage: Record<string, CardRuntimeCopy> = {
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
  const localized = language === 'ru' ? ru : language === 'el' ? el : language === 'fr' ? fr : language === 'es' ? es : language === 'de' ? de : language === 'th' ? th : language === 'ar' ? ar : language === 'ha' ? ha : language === 'tr' ? tr : en;
  return { ...localized, ...(runtimeByLanguage[language] || runtimeByLanguage.en) };
};
