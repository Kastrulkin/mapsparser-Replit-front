import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { newAuth } from '@/lib/auth_new';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  CircleDollarSign,
  ExternalLink,
  Globe,
  Mail,
  MapPin,
  MessageCircle,
  ShieldCheck,
  Sparkles,
  Star,
} from 'lucide-react';

type OfferPagePayload = {
  processing?: boolean;
  processing_message?: string;
  name?: string;
  display_name?: string;
  category?: string;
  city?: string;
  address?: string;
  source_url?: string;
  logo_url?: string | null;
  photo_urls?: string[];
  maps_analysis?: Array<{
    source?: string;
    label?: string;
    url?: string | null;
    rating?: number | null;
    reviews_total?: number | null;
    last_sync_at?: string | null;
  }>;
  audit?: {
    summary_score?: number;
    health_level?: string;
    health_label?: string;
    summary_text?: string;
    findings?: Array<{ title?: string; description?: string }>;
    recommended_actions?: Array<{ title?: string; description?: string }>;
    issue_blocks?: Array<{
      id?: string;
      section?: string;
      priority?: string;
      title?: string;
      problem?: string;
      evidence?: string;
      impact?: string;
      fix?: string;
    }>;
    top_3_issues?: Array<{
      id?: string;
      title?: string;
      priority?: string;
      problem?: string;
    }>;
    action_plan?: {
      next_24h?: string[];
      next_7d?: string[];
      ongoing?: string[];
    };
    audit_profile?: string;
    audit_profile_label?: string;
    best_fit_customer_profile?: string[];
    weak_fit_customer_profile?: string[];
    best_fit_guest_profile?: string[];
    weak_fit_guest_profile?: string[];
    search_intents_to_target?: string[];
    photo_shots_missing?: string[];
    editor_blocks?: {
      summary?: { title?: string; body?: string };
      strong_demand?: { title?: string; items?: string[] };
      weak_demand?: { title?: string; items?: string[] };
      why?: { title?: string; items?: string[] };
      top_issues?: {
        title?: string;
        items?: Array<{ title?: string; body?: string; priority?: string }>;
      };
      action_plan?: {
        title?: string;
        sections?: Array<{ key?: string; title?: string; items?: string[] }>;
      };
    };
    positioning_focus?: string[];
    strength_themes?: string[];
    objection_themes?: string[];
    services_preview?: Array<{
      current_name?: string;
      improved_name?: string;
      source?: string;
      category?: string;
      description?: string;
      price?: string;
    }>;
    reviews_preview?: Array<{ text?: string; author?: string; rating?: number; org_reply?: string }>;
    news_preview?: Array<{ title?: string; text?: string }>;
    subscores?: Record<string, number>;
    current_state?: {
      rating?: number | null;
      reviews_count?: number;
      unanswered_reviews_count?: number;
      services_count?: number;
      services_with_price_count?: number;
      has_website?: boolean;
      has_recent_activity?: boolean;
      photos_state?: string;
      unverified_locations_count?: number;
      verified_locations_count?: number;
      verification_unknown_locations_count?: number;
    };
    parse_context?: {
      last_parse_at?: string;
      last_parse_status?: string;
      no_new_services_found?: boolean;
    };
    cadence?: {
      news_posts_per_month_min?: number;
      photos_per_month_min?: number;
      reviews_response_hours_max?: number;
    };
    revenue_potential?: {
      total_min?: number;
      total_max?: number;
      dominant_driver?: string;
    };
  };
  preferred_language?: string;
  primary_language?: string;
  enabled_languages?: string[];
  available_languages?: string[];
  audit_full?: Record<string, any>;
  match?: {
    match_score?: number;
    score_explanation?: string;
    offer_angles?: string[];
  };
  message?: string | null;
  cta?: {
    telegram_url?: string | null;
    whatsapp_url?: string | null;
    email?: string | null;
    website?: string | null;
  };
  updated_at?: string;
};

type ReviewPreviewItem = {
  text?: string;
  review?: string;
  author?: string;
  name?: string;
  rating?: number;
  org_reply?: string;
  reply_preview?: string;
};
type NewsPreviewItem = { title?: string; text?: string; body?: string };

const formatNum = (value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  return Number(value).toLocaleString('ru-RU');
};

const UI_TEXT_BASE = {
  ru: {
    loading: 'Загрузка страницы оффера...',
    notFound: 'Страница оффера не найдена',
    companyLogo: 'Логотип компании',
    categoryMissing: 'Категория не указана',
    lastAudit: 'Последний аудит',
    processingFallback: 'Здесь появится ваш отчёт, как только он будет готов.',
    cardScore: 'Оценка карточки',
    stateUnknown: 'Состояние не определено',
    rating: 'Рейтинг',
    reviews: 'Отзывы',
    services: 'Услуги',
    monthlyPotential: 'Потенциал в месяц',
    estimateUnavailable: 'Оценка недоступна',
    currentStateTitle: 'Текущее состояние карточки',
    currentStateText: 'Это срез по ключевым зонам. Ниже сразу видно, что уже в порядке, а что теряет заявки.',
    stateServices: 'Услуги в карточке',
    stateWebsite: 'Сайт',
    stateReviews: 'Работа с отзывами',
    stateActivity: 'Активность карточки',
    found: 'найдено',
    servicesMissing: 'Не заполнены или не распознаны',
    websitePresent: 'Есть ссылка на сайт',
    websiteMissing: 'Сайт не указан',
    repliesExist: 'Ответы на отзывы есть',
    noAnswerPrefix: 'Без ответа',
    activityPresent: 'Есть свежие обновления',
    activityMissing: 'Нужны новости/обновления',
    allMapsTitle: 'Анализ всех доступных карт',
    allMapsText: 'Для этой компании найдены несколько карточек. Ниже видно, где именно сильнее социальное доказательство и где карточку нужно дотянуть.',
    bestReviews: 'Лучше по отзывам',
    bestRating: 'Лучше по рейтингу',
    priority: 'Приоритет',
    sourceFallback: 'Источник',
    open: 'Открыть',
    updated: 'Обновлено',
    improveFirstTitle: 'Что улучшить в первую очередь',
    issueFallback: 'Проблема',
    recommendationFallback: 'Рекомендация',
    noDescription: 'Описание не указано',
    problem: 'Проблема',
    fact: 'Факт',
    impact: 'Влияние',
    whatToDo: 'Что сделать',
    cadenceTitle: 'Регламент регулярной работы с карточкой',
    cadenceText: 'Новости и обновления: минимум {news} в месяц. Фото: минимум {photos} новых фото в месяц. Ответ на отзывы: до {hours} часов.',
    implementationPlan: 'План внедрения',
    in24h: 'За 24 часа',
    in7d: 'За 7 дней',
    ongoing: 'На постоянной основе',
    servicesTitle: 'Услуги в карточке',
    current: 'Сейчас',
    category: 'Категория',
    canShowLikeThis: 'Можно показать так',
    price: 'Цена',
    source: 'Источник',
    servicesUnavailable: 'Услуги не заполнены или недоступны в карточке.',
    photosTitle: 'Фото и визуал карточки',
    photoAlt: 'Фото {index}',
    activityTitle: 'Активность карточки',
    freshReviewsMissing: 'Свежих отзывов нет в срезе.',
    newsPosts: 'Новости/посты',
    newsMissing: 'Публикаций в срезе не найдено.',
    businessReply: 'Ответ бизнеса',
    nextTitle: 'Что делать дальше',
    nextText: 'Можно внедрить улучшения самостоятельно по шагам выше. Если нужна помощь, подключимся и сделаем это вместе с вами - стоимость от 1500 рублей в месяц.',
    optimizeMaps: 'Оптимизировать карты',
    contactExpert: 'Связаться с экспертом',
    contactTelegram: 'Связаться в Telegram',
    contactEmail: 'Написать на Email',
    goToWebsite: 'Перейти на сайт',
    openMapCard: 'Открыть карточку на карте',
    firstDraft: 'Черновик первого обращения',
    client: 'Клиент',
    mapStrengthReviews: 'Лучше по отзывам',
    mapStrengthRating: 'Лучше по рейтингу',
    priorityYandexReviews: 'Сначала стоит усилить Яндекс Карты: сейчас там на {gap} отзывов меньше, чем в Google Maps.',
    priorityYandexRating: 'Сначала стоит подтянуть Яндекс Карты: рейтинг там ниже, чем в Google Maps.',
    priorityGoogleReviews: 'Сначала стоит усилить Google Maps: там заметно меньше отзывов, чем в Яндекс Картах.',
    priorityGeneric: 'Сначала укрепите ту карту, где меньше отзывов и слабее социальное доказательство, затем выровняйте контент между всеми карточками.',
  },
  en: {
    loading: 'Loading audit page...',
    notFound: 'Offer page not found',
    companyLogo: 'Company logo',
    categoryMissing: 'Category is not specified',
    lastAudit: 'Last audit',
    processingFallback: 'Your report will appear here as soon as it is ready.',
    cardScore: 'Card score',
    stateUnknown: 'Status is not defined',
    rating: 'Rating',
    reviews: 'Reviews',
    services: 'Services',
    monthlyPotential: 'Monthly potential',
    estimateUnavailable: 'Estimate unavailable',
    currentStateTitle: 'Current card state',
    currentStateText: 'This is a quick snapshot of the key zones. You can immediately see what is already working well and what is costing inquiries.',
    stateServices: 'Services in the card',
    stateWebsite: 'Website',
    stateReviews: 'Review handling',
    stateActivity: 'Card activity',
    found: 'found',
    servicesMissing: 'Missing or not recognized',
    websitePresent: 'Website link is present',
    websiteMissing: 'Website is missing',
    repliesExist: 'Business replies are present',
    noAnswerPrefix: 'Unanswered',
    activityPresent: 'Fresh updates are present',
    activityMissing: 'Needs news and updates',
    allMapsTitle: 'All available maps analysis',
    allMapsText: 'We found multiple map listings for this business. Below you can see where social proof is stronger and which listing needs attention first.',
    bestReviews: 'Best by reviews',
    bestRating: 'Best by rating',
    priority: 'Priority',
    sourceFallback: 'Source',
    open: 'Open',
    updated: 'Updated',
    improveFirstTitle: 'What to improve first',
    issueFallback: 'Issue',
    recommendationFallback: 'Recommendation',
    noDescription: 'No description provided',
    problem: 'Problem',
    fact: 'Evidence',
    impact: 'Impact',
    whatToDo: 'What to do',
    cadenceTitle: 'Recommended operating cadence',
    cadenceText: 'News and updates: at least {news} per month. Photos: at least {photos} new photos per month. Review response time: within {hours} hours.',
    implementationPlan: 'Implementation plan',
    in24h: 'Within 24 hours',
    in7d: 'Within 7 days',
    ongoing: 'Ongoing',
    servicesTitle: 'Services in the card',
    current: 'Current',
    category: 'Category',
    canShowLikeThis: 'Suggested version',
    price: 'Price',
    source: 'Source',
    servicesUnavailable: 'Services are not filled in or are unavailable in the listing.',
    photosTitle: 'Photos and card visual quality',
    photoAlt: 'Photo {index}',
    activityTitle: 'Listing activity',
    freshReviewsMissing: 'No fresh reviews were found in the snapshot.',
    newsPosts: 'News / posts',
    newsMissing: 'No publications were found in the snapshot.',
    businessReply: 'Business reply',
    nextTitle: 'What to do next',
    nextText: 'You can implement the improvements yourself using the steps above. If you want help, we can do it with you — plans start from $15 per month.',
    optimizeMaps: 'Optimize map listings',
    contactExpert: 'Talk to an expert',
    contactTelegram: 'Contact via Telegram',
    contactEmail: 'Email us',
    goToWebsite: 'Visit website',
    openMapCard: 'Open listing on map',
    firstDraft: 'First outreach draft',
    client: 'Customer',
    mapStrengthReviews: 'Best by reviews',
    mapStrengthRating: 'Best by rating',
    priorityYandexReviews: 'Start by improving Yandex Maps: it currently has {gap} fewer reviews than Google Maps.',
    priorityYandexRating: 'Start by improving Yandex Maps: its rating is lower than Google Maps.',
    priorityGoogleReviews: 'Start by improving Google Maps: it has noticeably fewer reviews than Yandex Maps.',
    priorityGeneric: 'Start with the map listing that has fewer reviews and weaker social proof, then align the content across all cards.',
  },
  el: {
    loading: 'Φόρτωση της σελίδας ελέγχου...',
    notFound: 'Η σελίδα της προσφοράς δεν βρέθηκε',
    companyLogo: 'Λογότυπο εταιρείας',
    categoryMissing: 'Η κατηγορία δεν έχει οριστεί',
    lastAudit: 'Τελευταίος έλεγχος',
    processingFallback: 'Η αναφορά σας θα εμφανιστεί εδώ μόλις είναι έτοιμη.',
    cardScore: 'Βαθμολογία καταχώρισης',
    stateUnknown: 'Η κατάσταση δεν ορίστηκε',
    rating: 'Βαθμολογία',
    reviews: 'Κριτικές',
    services: 'Υπηρεσίες',
    monthlyPotential: 'Μηνιαίο δυναμικό',
    estimateUnavailable: 'Η εκτίμηση δεν είναι διαθέσιμη',
    currentStateTitle: 'Τρέχουσα κατάσταση καταχώρισης',
    currentStateText: 'Αυτό είναι ένα γρήγορο στιγμιότυπο των βασικών σημείων. Φαίνεται αμέσως τι λειτουργεί ήδη καλά και τι κοστίζει αιτήματα.',
    stateServices: 'Υπηρεσίες στην καταχώριση',
    stateWebsite: 'Ιστότοπος',
    stateReviews: 'Διαχείριση κριτικών',
    stateActivity: 'Δραστηριότητα καταχώρισης',
    found: 'βρέθηκαν',
    servicesMissing: 'Δεν υπάρχουν ή δεν αναγνωρίστηκαν',
    websitePresent: 'Υπάρχει σύνδεσμος ιστοτόπου',
    websiteMissing: 'Ο ιστότοπος λείπει',
    repliesExist: 'Υπάρχουν απαντήσεις της επιχείρησης',
    noAnswerPrefix: 'Χωρίς απάντηση',
    activityPresent: 'Υπάρχουν πρόσφατες ενημερώσεις',
    activityMissing: 'Χρειάζονται νέα και ενημερώσεις',
    allMapsTitle: 'Ανάλυση όλων των διαθέσιμων χαρτών',
    allMapsText: 'Βρέθηκαν πολλαπλές καταχωρίσεις χαρτών για αυτή την επιχείρηση. Παρακάτω φαίνεται πού είναι ισχυρότερη η κοινωνική απόδειξη και ποια καταχώριση χρειάζεται προτεραιότητα.',
    bestReviews: 'Καλύτερο σε κριτικές',
    bestRating: 'Καλύτερο σε βαθμολογία',
    priority: 'Προτεραιότητα',
    sourceFallback: 'Πηγή',
    open: 'Άνοιγμα',
    updated: 'Ενημερώθηκε',
    improveFirstTitle: 'Τι να βελτιώσετε πρώτα',
    issueFallback: 'Ζήτημα',
    recommendationFallback: 'Σύσταση',
    noDescription: 'Δεν υπάρχει περιγραφή',
    problem: 'Πρόβλημα',
    fact: 'Στοιχείο',
    impact: 'Επίδραση',
    whatToDo: 'Τι να κάνετε',
    cadenceTitle: 'Προτεινόμενος ρυθμός εργασίας',
    cadenceText: 'Νέα και ενημερώσεις: τουλάχιστον {news} τον μήνα. Φωτογραφίες: τουλάχιστον {photos} νέες φωτογραφίες τον μήνα. Απάντηση σε κριτικές: εντός {hours} ωρών.',
    implementationPlan: 'Πλάνο υλοποίησης',
    in24h: 'Μέσα σε 24 ώρες',
    in7d: 'Μέσα σε 7 ημέρες',
    ongoing: 'Σε συνεχή βάση',
    servicesTitle: 'Υπηρεσίες στην καταχώριση',
    current: 'Τώρα',
    category: 'Κατηγορία',
    canShowLikeThis: 'Προτεινόμενη εκδοχή',
    price: 'Τιμή',
    source: 'Πηγή',
    servicesUnavailable: 'Οι υπηρεσίες δεν είναι συμπληρωμένες ή δεν είναι διαθέσιμες στην καταχώριση.',
    photosTitle: 'Φωτογραφίες και οπτική ποιότητα',
    photoAlt: 'Φωτογραφία {index}',
    activityTitle: 'Δραστηριότητα καταχώρισης',
    freshReviewsMissing: 'Δεν βρέθηκαν πρόσφατες κριτικές στο στιγμιότυπο.',
    newsPosts: 'Νέα / δημοσιεύσεις',
    newsMissing: 'Δεν βρέθηκαν δημοσιεύσεις στο στιγμιότυπο.',
    businessReply: 'Απάντηση επιχείρησης',
    nextTitle: 'Τι να κάνετε μετά',
    nextText: 'Μπορείτε να εφαρμόσετε μόνοι σας τις βελτιώσεις με τα παραπάνω βήματα. Αν χρειάζεστε βοήθεια, μπορούμε να το κάνουμε μαζί σας — τα πλάνα ξεκινούν από $12 τον μήνα.',
    optimizeMaps: 'Βελτιστοποίηση χαρτών',
    contactExpert: 'Μιλήστε με ειδικό',
    contactTelegram: 'Επικοινωνία στο Telegram',
    contactEmail: 'Στείλτε email',
    goToWebsite: 'Μετάβαση στον ιστότοπο',
    openMapCard: 'Άνοιγμα καταχώρισης στον χάρτη',
    firstDraft: 'Πρώτο προσχέδιο επικοινωνίας',
    client: 'Πελάτης',
    mapStrengthReviews: 'Καλύτερο σε κριτικές',
    mapStrengthRating: 'Καλύτερο σε βαθμολογία',
    priorityYandexReviews: 'Ξεκινήστε ενισχύοντας το Yandex Maps: αυτή τη στιγμή έχει {gap} λιγότερες κριτικές από το Google Maps.',
    priorityYandexRating: 'Ξεκινήστε ενισχύοντας το Yandex Maps: η βαθμολογία του είναι χαμηλότερη από το Google Maps.',
    priorityGoogleReviews: 'Ξεκινήστε ενισχύοντας το Google Maps: έχει αισθητά λιγότερες κριτικές από το Yandex Maps.',
    priorityGeneric: 'Ξεκινήστε από την καταχώριση που έχει λιγότερες κριτικές και πιο αδύναμη κοινωνική απόδειξη, και στη συνέχεια ευθυγραμμίστε το περιεχόμενο σε όλες τις κάρτες.',
  },
  tr: {
    loading: 'Denetim sayfası yükleniyor...',
    notFound: 'Teklif sayfası bulunamadı',
    companyLogo: 'Şirket logosu',
    categoryMissing: 'Kategori belirtilmedi',
    lastAudit: 'Son denetim',
    processingFallback: 'Raporunuz hazır olur olmaz burada görünecek.',
    cardScore: 'Kart puanı',
    stateUnknown: 'Durum belirlenemedi',
    rating: 'Puan',
    reviews: 'Yorumlar',
    services: 'Hizmetler',
    monthlyPotential: 'Aylık potansiyel',
    estimateUnavailable: 'Tahmin mevcut değil',
    currentStateTitle: 'Kartın mevcut durumu',
    currentStateText: 'Bu, temel alanların hızlı bir özetidir. Neyin iyi çalıştığı ve hangi eksiklerin talep kaybettirdiği hemen görünür.',
    stateServices: 'Karttaki hizmetler',
    stateWebsite: 'Web sitesi',
    stateReviews: 'Yorum yönetimi',
    stateActivity: 'Kart aktivitesi',
    found: 'bulundu',
    servicesMissing: 'Eksik veya tanınmadı',
    websitePresent: 'Web sitesi bağlantısı mevcut',
    websiteMissing: 'Web sitesi yok',
    repliesExist: 'İşletme yanıtları mevcut',
    noAnswerPrefix: 'Yanıtsız',
    activityPresent: 'Güncel içerik var',
    activityMissing: 'Haber ve güncelleme gerekiyor',
    allMapsTitle: 'Tüm mevcut harita profillerinin analizi',
    allMapsText: 'Bu işletme için birden fazla harita profili bulundu. Aşağıda sosyal kanıtın nerede daha güçlü olduğu ve önce hangi profilin iyileştirilmesi gerektiği görünüyor.',
    bestReviews: 'Yorumlarda daha güçlü',
    bestRating: 'Puanı daha yüksek',
    priority: 'Öncelik',
    sourceFallback: 'Kaynak',
    open: 'Aç',
    updated: 'Güncellendi',
    improveFirstTitle: 'Önce neyi iyileştirmeli',
    issueFallback: 'Sorun',
    recommendationFallback: 'Öneri',
    noDescription: 'Açıklama yok',
    problem: 'Sorun',
    fact: 'Kanıt',
    impact: 'Etkisi',
    whatToDo: 'Ne yapılmalı',
    cadenceTitle: 'Önerilen çalışma ritmi',
    cadenceText: 'Haber ve güncellemeler: ayda en az {news}. Fotoğraflar: ayda en az {photos} yeni fotoğraf. Yorum yanıt süresi: en geç {hours} saat içinde.',
    implementationPlan: 'Uygulama planı',
    in24h: '24 saat içinde',
    in7d: '7 gün içinde',
    ongoing: 'Sürekli',
    servicesTitle: 'Karttaki hizmetler',
    current: 'Şu an',
    category: 'Kategori',
    canShowLikeThis: 'Önerilen versiyon',
    price: 'Fiyat',
    source: 'Kaynak',
    servicesUnavailable: 'Hizmetler kartta doldurulmamış veya görüntülenemiyor.',
    photosTitle: 'Fotoğraflar ve görsel kalite',
    photoAlt: 'Fotoğraf {index}',
    activityTitle: 'Kart aktivitesi',
    freshReviewsMissing: 'Kesitte yeni yorum bulunamadı.',
    newsPosts: 'Haberler / gönderiler',
    newsMissing: 'Kesitte yayın bulunamadı.',
    businessReply: 'İşletme yanıtı',
    nextTitle: 'Sonraki adım',
    nextText: 'Yukarıdaki adımlarla iyileştirmeleri kendiniz uygulayabilirsiniz. Destek isterseniz bunu birlikte yapabiliriz.',
    optimizeMaps: 'Harita profillerini optimize et',
    contactExpert: 'Uzmanla görüş',
    contactTelegram: 'Telegram üzerinden yaz',
    contactEmail: 'E-posta gönder',
    goToWebsite: 'Web sitesine git',
    openMapCard: 'Harita profilini aç',
    firstDraft: 'İlk iletişim taslağı',
    client: 'Müşteri',
    mapStrengthReviews: 'Yorumlarda daha güçlü',
    mapStrengthRating: 'Puanı daha yüksek',
    priorityYandexReviews: 'Önce Yandex Maps profilini güçlendirin: şu anda Google Maps\'ten {gap} daha az yoruma sahip.',
    priorityYandexRating: 'Önce Yandex Maps profilini iyileştirin: puanı Google Maps\'ten daha düşük.',
    priorityGoogleReviews: 'Önce Google Maps profilini güçlendirin: Yandex Maps\'e göre belirgin şekilde daha az yoruma sahip.',
    priorityGeneric: 'Önce daha az yoruma ve daha zayıf sosyal kanıta sahip profili güçlendirin, sonra tüm kartlar arasında içeriği hizalayın.',
  },
  ar: {
    loading: 'جارٍ تحميل صفحة التدقيق...',
    notFound: 'لم يتم العثور على صفحة العرض',
    companyLogo: 'شعار الشركة',
    categoryMissing: 'الفئة غير محددة',
    lastAudit: 'آخر تدقيق',
    processingFallback: 'سيظهر تقريرك هنا فور جاهزيته.',
    cardScore: 'تقييم البطاقة',
    stateUnknown: 'الحالة غير محددة',
    rating: 'التقييم',
    reviews: 'المراجعات',
    services: 'الخدمات',
    monthlyPotential: 'الإمكانات الشهرية',
    estimateUnavailable: 'التقدير غير متاح',
    currentStateTitle: 'الحالة الحالية للبطاقة',
    currentStateText: 'هذه لقطة سريعة للمناطق الأساسية. يظهر فوراً ما الذي يعمل جيداً بالفعل وما الذي يسبب فقدان الطلبات.',
    stateServices: 'الخدمات في البطاقة',
    stateWebsite: 'الموقع الإلكتروني',
    stateReviews: 'إدارة المراجعات',
    stateActivity: 'نشاط البطاقة',
    found: 'تم العثور',
    servicesMissing: 'مفقودة أو غير معروفة',
    websitePresent: 'يوجد رابط للموقع',
    websiteMissing: 'الموقع غير موجود',
    repliesExist: 'توجد ردود من النشاط التجاري',
    noAnswerPrefix: 'بدون رد',
    activityPresent: 'توجد تحديثات حديثة',
    activityMissing: 'تحتاج إلى أخبار وتحديثات',
    allMapsTitle: 'تحليل جميع بطاقات الخرائط المتاحة',
    allMapsText: 'وجدنا أكثر من بطاقة خرائط لهذا النشاط. في الأسفل ستظهر البطاقة الأقوى من حيث الدليل الاجتماعي وأي بطاقة تحتاج إلى أولوية في التحسين.',
    bestReviews: 'الأفضل من حيث المراجعات',
    bestRating: 'الأفضل من حيث التقييم',
    priority: 'الأولوية',
    sourceFallback: 'المصدر',
    open: 'فتح',
    updated: 'تم التحديث',
    improveFirstTitle: 'ما الذي يجب تحسينه أولاً',
    issueFallback: 'المشكلة',
    recommendationFallback: 'التوصية',
    noDescription: 'لا يوجد وصف',
    problem: 'المشكلة',
    fact: 'الدليل',
    impact: 'الأثر',
    whatToDo: 'ما الذي يجب فعله',
    cadenceTitle: 'إيقاع العمل الموصى به',
    cadenceText: 'الأخبار والتحديثات: على الأقل {news} شهرياً. الصور: على الأقل {photos} صور جديدة شهرياً. الرد على المراجعات: خلال {hours} ساعة.',
    implementationPlan: 'خطة التنفيذ',
    in24h: 'خلال 24 ساعة',
    in7d: 'خلال 7 أيام',
    ongoing: 'بشكل مستمر',
    servicesTitle: 'الخدمات في البطاقة',
    current: 'الحالي',
    category: 'الفئة',
    canShowLikeThis: 'النسخة المقترحة',
    price: 'السعر',
    source: 'المصدر',
    servicesUnavailable: 'الخدمات غير مملوءة أو غير متاحة في البطاقة.',
    photosTitle: 'الصور والجودة البصرية للبطاقة',
    photoAlt: 'صورة {index}',
    activityTitle: 'نشاط البطاقة',
    freshReviewsMissing: 'لم يتم العثور على مراجعات حديثة في هذه اللقطة.',
    newsPosts: 'الأخبار / المنشورات',
    newsMissing: 'لم يتم العثور على منشورات في هذه اللقطة.',
    businessReply: 'رد النشاط التجاري',
    nextTitle: 'ما الخطوة التالية',
    nextText: 'يمكنك تنفيذ التحسينات بنفسك عبر الخطوات أعلاه. وإذا أردت المساعدة، يمكننا تنفيذها معك.',
    optimizeMaps: 'تحسين بطاقات الخرائط',
    contactExpert: 'تواصل مع خبير',
    contactTelegram: 'التواصل عبر تيليجرام',
    contactEmail: 'راسلنا عبر البريد',
    goToWebsite: 'الانتقال إلى الموقع',
    openMapCard: 'فتح البطاقة على الخريطة',
    firstDraft: 'المسودة الأولى للتواصل',
    client: 'العميل',
    mapStrengthReviews: 'الأفضل من حيث المراجعات',
    mapStrengthRating: 'الأفضل من حيث التقييم',
    priorityYandexReviews: 'ابدأ بتحسين Yandex Maps: لديها الآن {gap} مراجعة أقل من Google Maps.',
    priorityYandexRating: 'ابدأ بتحسين Yandex Maps: تقييمها أقل من Google Maps.',
    priorityGoogleReviews: 'ابدأ بتحسين Google Maps: لديها مراجعات أقل بشكل ملحوظ من Yandex Maps.',
    priorityGeneric: 'ابدأ ببطاقة الخرائط التي تملك مراجعات أقل ودليلاً اجتماعياً أضعف، ثم وحّد المحتوى عبر جميع البطاقات.',
  },
};

type PageLang = 'ru' | 'en' | 'fr' | 'es' | 'el' | 'de' | 'th' | 'ar' | 'ha' | 'tr';

const supportedPublicAuditLanguages: PageLang[] = ['ru', 'en', 'fr', 'es', 'el', 'de', 'th', 'ar', 'ha', 'tr'];

const isPageLang = (value: string): value is PageLang =>
  value === 'ru' || value === 'en' || value === 'fr' || value === 'es' || value === 'el' || value === 'de' || value === 'th' || value === 'ar' || value === 'ha' || value === 'tr';

const normalizePageLanguages = (value?: string[] | null): PageLang[] => {
  const result: PageLang[] = [];
  if (Array.isArray(value)) {
    value.forEach((item) => {
      const code = String(item || '').trim().toLowerCase();
      if ((code === 'ru' || code === 'en' || code === 'fr' || code === 'es' || code === 'el' || code === 'de' || code === 'th' || code === 'ar' || code === 'ha' || code === 'tr') && !result.includes(code)) {
        result.push(code);
      }
    });
  }
  return result;
};

const UI_TEXT: Record<PageLang, typeof UI_TEXT_BASE.ru> = {
  ...UI_TEXT_BASE,
  fr: UI_TEXT_BASE.en,
  es: UI_TEXT_BASE.en,
  de: UI_TEXT_BASE.en,
  th: UI_TEXT_BASE.en,
  ar: UI_TEXT_BASE.ar,
  ha: UI_TEXT_BASE.en,
};

const AUDIT_TEXT_TRANSLATIONS = {
  en: {
    'Есть точки роста': 'There is room to grow',
    'Сильная карточка': 'Strong listing',
    'Карточка теряет клиентов': 'The listing is losing customers',
    'Готовим отчёт': 'Preparing the report',
    'Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.':
      'We are already parsing the listing and collecting data. This usually takes 1–3 minutes.',
    'Отчёт готовится дольше обычного. Мы продолжаем обработку данных.':
      'The report is taking longer than usual. We are still processing the data.',
    'Нет структуры услуг': 'No service structure',
    'Нет актуальных фото': 'No recent photos',
    'Карточка выглядит неактивной': 'The listing looks inactive',
    'В карточке не видно активного списка услуг.': 'No active service list is visible in the listing.',
    'В карточке не видно визуального подтверждения качества.': 'There is no visual proof of quality in the listing.',
    'Нет регулярных признаков ведения карточки.': 'There are no regular signs that the listing is being actively maintained.',
    'Добавить ключевые услуги с категориями, описаниями и ценами.':
      'Add core services with categories, descriptions, and prices.',
    'Добавить свежие фото работ, команды или интерьера.':
      'Add fresh photos of your work, team, or interior.',
    'Публиковать не менее 4 обновлений в месяц и добавлять новые фото.':
      'Publish at least 4 updates per month and add new photos regularly.',
    'За 24 часа': 'Within 24 hours',
    'За 7 дней': 'Within 7 days',
    'На постоянной основе': 'Ongoing',
    'Публиковать новости/обновления минимум 4 раз(а) в месяц.':
      'Publish news and updates at least 4 times per month.',
    'Добавлять новые фото минимум 8 раз(а) в месяц.':
      'Add new photos at least 8 times per month.',
    'Отвечать на отзывы не позднее 48 часов.':
      'Reply to reviews within 48 hours.',
    'Добавить описание, которое объясняет бизнес как решение задачи: кто вы, кому помогаете, с чем к вам приходят и почему выбрать именно вас, а не соседнюю карточку.':
      'Add a description that explains the business as a solution: who you are, whom you help, what people come to you for, and why they should choose you over the listing next door.',
    'Собрать 5–10 ключевых услуг или товарных групп как отдельные точки входа в спрос, чтобы карточка перестала быть абстрактной визиткой.':
      'Build 5–10 core services or product groups as separate demand entry points so the listing stops looking like an abstract business card.',
    'Проверить категории, контакты и атрибуты, чтобы карточка соответствовала не общему профилю бизнеса, а конкретным коммерческим сценариям поиска.':
      'Review categories, contacts, and attributes so the listing matches real commercial search scenarios rather than just a generic business profile.',
    'Подготовить 3–5 updates, которые отвечают на реальный входящий спрос: кейсы, новые услуги, частые вопросы, сезонные предложения и рабочие процессы.':
      'Prepare 3–5 updates that answer real incoming demand: cases, new services, FAQs, seasonal offers, and how the work is delivered.',
    'Поддерживать актуальность услуг, цен, фото и контактов, чтобы карточка не расходилась с реальностью.':
      'Keep services, prices, photos, and contacts up to date so the listing stays aligned with reality.',
    'Регулярно отвечать на отзывы и превращать их в понятный social proof, а не просто закрывать долг.':
      'Reply to reviews consistently and turn them into clear social proof instead of just closing a backlog item.',
    'Держать карточку живой через кейсы, обновления и визуальные подтверждения реальной работы.':
      'Keep the listing alive with cases, updates, and visual proof of real work.',
    'Для локального бизнеса важны регулярные фото, updates, ответы на отзывы и актуальные услуги.':
      'For a local business, regular photos, updates, review replies, and up-to-date services matter.',
    'Добавить описание: кто вы, какие задачи решаете, в чём сильные стороны и что клиент получает на выходе.':
      'Add a description that explains who you are, what problems you solve, what your strengths are, and what the customer gets in the end.',
    'Есть точки роста. Карточка Knight Mobile Maintenance: рейтинг 4.8, отзывов 5, услуг 0. Сайт: нет, свежая активность: есть. Основной потенциал роста сейчас в структуре услуг.':
      'There is room to grow. Knight Mobile Maintenance: rating 4.8, reviews 5, services 0. Website: no, fresh activity: yes. The main growth opportunity right now is the service structure.',
    'Заполнить отсутствующие контакты и проверить кликабельность ссылок.':
      'Fill in the missing contacts and make sure the links are clickable.',
    'Запустить сбор отзывов после визита и закрепить еженедельный ритм.':
      'Start asking for reviews after each visit and lock in a weekly collection rhythm.',
    'Карточке не хватает сигналов активности':
      'The listing lacks activity signals',
    'Клиенту сложно быстро понять, зачем сюда обращаться.':
      'It is hard for a customer to quickly understand why they should contact this business.',
    'Описание карточки не объясняет ценность бизнеса':
      'The listing description does not explain the business value.',
    'Карточка не даёт понять, что это за бизнес, для кого он и с чем сюда обращаться.':
      'The listing does not make it clear what this business is, who it is for, or what people should contact it about.',
    'Общее описание без структуры':
      'Generic description with no structure',
    'Нет цены или формата':
      'No price or service format',
    'Ключевая услуга с понятным названием':
      'Core service with a clear name',
    'Ключевые услуги или товарные группы':
      'Core services or product groups',
    'Команда, рабочая зона и примеры результата':
      'Team, work area, and examples of results',
    'Локальный бизнес':
      'Local business',
    'Fashion / designer studio':
      'Fashion / designer studio',
    'Клиенты, которые ищут custom dresses и bridal wear в Lahore':
      'Clients looking for custom dresses and bridal wear in Lahore',
    'Покупатели, которым важны premium stitching, индивидуальный подход и fittings':
      'Clients who care about premium stitching, a custom approach, and fittings',
    'Аудитория, которая сравнивает bridal designer, formal wear studio и custom tailoring':
      'People comparing bridal designers, formal wear studios, and custom tailoring',
    'Пользователи, которые ждут ready-to-buy магазин, если студия работает под custom заказ':
      'Users who expect a ready-to-buy store even though the studio works on custom orders',
    'Новый трафик, если карточка не объясняет dress categories, pricing logic и процесс пошива':
      'New traffic will bounce if the listing does not explain dress categories, pricing logic, and the stitching process',
    'Bridal dresses, custom dresses и signature looks по категориям':
      'Bridal dresses, custom dresses, and signature looks grouped by category',
    'Stitching process, fittings, выбор тканей и детали пошива':
      'Stitching process, fittings, fabric selection, and tailoring details',
    'Студия, команда, консультационная зона и готовые образы на клиентах или манекенах':
      'Studio, team, consultation area, and finished looks on clients or mannequins',
    'Объяснить, какие типы платьев и заказов студия делает лучше всего':
      'Explain which types of dresses and orders the studio does best',
    'Разделить bridal, formal и custom stitching как отдельные точки входа в спрос':
      'Separate bridal, formal wear, and custom stitching into distinct demand entry points',
    'Усилить доверие через fit-story, процесс пошива и отзывы клиентов':
      'Build trust through fit stories, the tailoring process, and customer reviews',
    'Есть точки роста. У карточки уже есть базовый trust signal через рейтинг, но она почти не объясняет, что именно студия делает и по каким запросам её можно находить. Главные зоны роста сейчас — SEO-описание, структура услуг под bridal/custom спрос, review engine и регулярный визуальный контент.':
      'There is room to grow. The listing already has a baseline trust signal through its rating, but it barely explains what the studio actually does or which searches should surface it. The main growth levers right now are an SEO description, a bridal/custom service structure, a review engine, and steady visual content.',
    'Переписать описание карточки под SEO спрос: custom dresses, bridal wear, stitching, designer studio, Lahore.':
      'Rewrite the listing description for SEO demand: custom dresses, bridal wear, stitching, designer studio, Lahore.',
    'Добавить 10–15 услуг как отдельные точки входа в спрос: bridal dresses, custom dresses, bridal consultation, formal wear, stitching, fittings.':
      'Add 10–15 services as separate demand entry points: bridal dresses, custom dresses, bridal consultation, formal wear, stitching, fittings.',
    'Запустить review engine: собрать первые 15–30 отзывов через WhatsApp, после выдачи заказа и после примерки.':
      'Launch a review engine: collect the first 15–30 reviews through WhatsApp, after order delivery, and after fittings.',
    'Разбить фото на серии: bridal dresses, custom dresses, stitching process, fittings, готовые образы и детали пошива.':
      'Split photos into series: bridal dresses, custom dresses, stitching process, fittings, finished looks, and tailoring details.',
    'Проверить категории и позиционирование: fashion designer / bridal designer / custom dresses / stitching / boutique.':
      'Review categories and positioning: fashion designer / bridal designer / custom dresses / stitching / boutique.',
    'Запустить недельный контент-ритм: 1 post в неделю и 2–3 новых фото в неделю с кейсами, процессом и готовыми образами.':
      'Start a weekly content rhythm: 1 post per week and 2–3 new photos per week featuring cases, process, and finished looks.',
    'Держать в карточке актуальные направления: bridal, formal, custom stitching, consultations и сезонные коллекции.':
      'Keep the listing updated with current directions: bridal, formal wear, custom stitching, consultations, and seasonal collections.',
    'Отвечать на каждый отзыв, усиливая trust layer через quality, fit, premium stitching и bridal expertise.':
      'Reply to every review and strengthen the trust layer through quality, fit, premium stitching, and bridal expertise.',
    'Поддерживать живую карточку через weekly posts, новые фотосерии и кейсы клиентов.':
      'Keep the listing alive through weekly posts, new photo series, and customer case stories.',
    'Люди, которые ищут конкретную услугу рядом в вашем городе':
      'People looking for a specific service nearby in your city',
    'Новый трафик, если карточка не объясняет формат услуги и её результат':
      'New traffic will bounce if the listing does not explain the service format and its outcome.',
    'Новым клиентам сложнее доверять карточке.':
      'It is harder for new customers to trust the listing.',
    'Объём social proof пока слабый.':
      'The amount of social proof is still weak.',
    'Оценка ориентировочная и основана на модели карточки, а не на полном доступе к вашим продажам.':
      'This estimate is directional and based on the listing model, not on full access to your sales data.',
    'Падает доверие и карточка хуже конвертирует в обращение.':
      'Trust drops and the listing converts worse into inquiries.',
    'Пользователи, которым важны доверие, понятный прайс и удобный контакт':
      'Users who care about trust, transparent pricing, and easy contact',
    'Превратить карточку из визитки в понятную точку входа в спрос':
      'Turn the listing from a business card into a clear demand entry point',
    'Публиковать обновления, кейсы, новости и новые фото на регулярной основе.':
      'Publish updates, case studies, news, and new photos on a regular basis.',
    'Сейчас отзывов: 5, ориентир: 30+.':
      'Current reviews: 5, target: 30+.',
    'Сейчас услуг: 0.':
      'Current services: 0.',
    'Снижается freshness, доверие и вероятность обращения.':
      'Freshness, trust, and the likelihood of an inquiry are decreasing.',
    'Собрать ключевые услуги или категории предложения как отдельные, понятные и коммерчески полезные позиции.':
      'Build core services or offer categories as separate, clear, commercially useful items.',
    'У Knight Mobile Maintenance нет сильного описания под локальный спрос в .':
      'Knight Mobile Maintenance does not yet have a strong description aligned with local demand in its area.',
    'Усилить доверие через контакты, фото и конкретику по услугам':
      'Strengthen trust through contacts, photos, and specific service details',
    'Фасад или вход, чтобы бизнес было легко найти':
      'Facade or entrance so the business is easy to find',
    'Часть потенциальных клиентов не доходит до контакта.':
      'Some potential customers drop off before making contact.',
    'Это повышает доверие и сокращает путь до первого обращения.':
      'This builds trust and shortens the path to the first inquiry.',
    'конкретная услуга + вашем городе':
      'specific service + your city',
    'магазин': 'shop',
    'услуга рядом вашем городе':
      'service nearby in your city',
    'цена / отзывы / запись вашем городе':
      'price / reviews / booking in your city',
    'Собираем фактические данные карточки': 'Collecting real listing data',
    'Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.':
      'We are pulling services, reviews, rating, photos, and contacts from the map listing.',
    'Формируем персональный аудит': 'Building a personalized audit',
    'После парсинга покажем конкретные шаги роста именно для вашей карточки.':
      'After parsing, we will show concrete growth steps specifically for your listing.',
    'Аудит карточки на картах': 'Map listing audit',
    'Гости, которые ищут спокойное размещение в Fatih':
      'Guests looking for a calm stay in Fatih.',
    'Семьи и пары, которым важны простор, бассейн и понятный формат отдыха':
      'Families and couples who value space, a pool, and a clear holiday format.',
    'Путешественники, которым удобно передвигаться на машине':
      'Travellers who prefer getting around by car.',
    'Те, кто ценит: кухня, чистота':
      'Guests who care about: kitchen facilities, cleanliness.',
    'Гости, которые ожидают первую линию и мгновенный доступ к пляжу':
      'Guests who expect a first-line location and immediate beach access.',
    'Путешественники, которым важен формат классического hotel-by-the-sea':
      'Travellers looking for a classic hotel-by-the-sea format.',
    'Фасад и вход, чтобы объект было легко узнать':
      'Facade and entrance photos so the property is easy to recognize.',
    'Номера или апартаменты целиком: спальня, гостиная, кухня':
      'Full-room or apartment shots: bedroom, living area, kitchen.',
    'Бассейн, парковка и реальная окружающая инфраструктура':
      'Pool, parking, and the real surrounding infrastructure.',
    'Фото, которые честно показывают путь и расстояние до ключевых точек':
      'Photos that honestly show the route and distance to key points.',
    'Гостеприимство / размещение': 'Hospitality / accommodation',
    'Гости, которые ищут спокойное размещение в Fethiye':
      'Guests looking for a calm stay in Fethiye',
    'Те, кто ценит: cleanliness, тихая локация, бассейн':
      'Guests who care about: cleanliness, quiet location, pool',
    'Фасад, вывеска и вход, чтобы объект было легко узнать на месте':
      'Facade, signage, and entrance photos so the property is easy to recognize on arrival.',
    'Номера или апартаменты целиком: спальня, ванная, гостиная, kitchen':
      'Full-room or apartment shots: bedroom, bathroom, living area, kitchen.',
    'Номера или апартаменты целиком: спальня, ванная, гостиная, кухня':
      'Full-room or apartment shots: bedroom, bathroom, living area, kitchen.',
    'Завтраки, зона reception, бассейн, парковка и реальные удобства объекта':
      'Breakfast, reception area, pool, parking, and the real on-property amenities.',
    'Фото вида из окна, ближайшей инфраструктуры и реального пути до ключевых точек':
      'Photos of the view, nearby infrastructure, and the real route to key points.',
    'Ответа пока нет': 'No reply yet',
    'Описание не продаёт объект под поисковое намерение':
      'The description does not sell the property for search intent.',
    'Карточка не объясняет, что это за формат отдыха и кому он подходит.':
      'The listing does not explain the stay format or who it suits best.',
    'У объекта Oludenizevleri нет сильного описания под сценарии поиска по Fethiye.':
      'Oludenizevleri does not yet have a strong description tailored to search scenarios in Fethiye.',
    'Недостаточно сигналов активности':
      'Not enough activity signals.',
    'Карточка не выглядит как живой активный объект.':
      'The listing does not look like a live, actively managed property.',
    'Вместо услуг отображаются booking-offers или абстрактные позиции':
      'Booking offers or abstract placeholders are shown instead of real services.',
    'Карточка не показывает реальное предложение объекта как SEO-единицы.':
      'The listing does not present the property’s real offer as an SEO entry point.',
    'Карточка хуже ранжируется под сценарные запросы и слабее продаёт ценность объекта.':
      'The listing ranks worse for intent-driven searches and sells the property value less effectively.',
    'Booking-offer позиций: 0. Реальных услуг/amenities: нет.':
      'Booking-offer entries: 0. Real services/amenities: none.',
    'Показывать не агрегаторы бронирования, а реальное предложение: тип размещения, wellness/spa-процедуры, amenities, family-friendly features, parking, pool, kitchen.':
      'Show the real offer instead of booking aggregators: stay format, wellness/spa services, amenities, family-friendly features, parking, pool, kitchen.',
    'Объём review engine ещё не даёт устойчивого преимущества':
      'The review engine still does not provide a durable advantage.',
    'Карточке не хватает свежих управляемых отзывов, чтобы перекрывать слабую репутацию и усиливать social proof.':
      'The listing still lacks enough fresh, managed reviews to offset weak reputation and strengthen social proof.',
    'Репутация растёт медленно, а новый спрос дольше колеблется перед бронированием.':
      'Reputation grows slowly, and new demand hesitates longer before booking.',
    'Сейчас отзывов: 16. Для hotel-кейса этого ещё мало, чтобы уверенно выигрывать локальную конкуренцию при среднем рейтинге.':
      'Reviews now: 16. For a hotel case, this is still not enough to confidently win local competition at an average rating.',
    'Запустить сбор отзывов по сценарию после визита и просить конкретику про локацию, чистоту, сервис и удобство проживания.':
      'Launch a post-stay review collection flow and ask for specifics about location, cleanliness, service, and stay comfort.',
    'Категории, атрибуты и trust-triggers недораскрывают формат объекта':
      'Categories, attributes, and trust triggers do not fully explain the property format.',
    'Карточка не использует все сигналы, которые помогают туристу быстро понять уровень и формат проживания.':
      'The listing does not use all the signals that help a traveller quickly understand the level and stay format.',
    'Карточка теряет часть поисковых сценариев и хуже конвертирует холодный туристический трафик.':
      'The listing loses part of the search demand and converts cold travel traffic less effectively.',
    'Для hotel-кейсов особенно важны категории, nearby context и понятные promises: breakfast, Wi-Fi, airport transfer, family stay, 24/7 reception.':
      'For hotel cases, categories, nearby context, and clear promises matter most: breakfast, Wi-Fi, airport transfer, family stay, 24/7 reception.',
    'Проверить категории и атрибуты, а в тексте и карточке явно показать реальные trust-triggers, если они доступны.':
      'Review categories and attributes, and clearly show real trust triggers in the copy and listing where available.',
    'Карточка недоиспользует landmark и nearby-intent запросы':
      'The listing underuses landmark and nearby-intent searches.',
    'Отель можно находить не только по названию, но и по сценариям рядом с ключевыми точками района.':
      'The hotel can be found not only by name, but also through scenarios near key points in the area.',
    'Карточка недополучает трафик из туристических сценариев поиска и слабее конкурирует с более конкретно упакованными объектами.':
      'The listing misses traffic from travel search scenarios and competes less effectively against more concretely packaged properties.',
    'Для hospitality в Fethiye важны nearby-intent формулировки: old city / landmark / airport / family stay / budget stay.':
      'For hospitality in Fethiye, nearby-intent phrasing matters: old city / landmark / airport / family stay / budget stay.',
    'Добавить в описание, posts и ответы на отзывы nearby-intent сценарии: near landmark, old city, airport convenience, family stay, quiet stay — только там, где это соответствует фактической локации объекта.':
      'Add nearby-intent scenarios to the description, posts, and review replies: near landmark, old city, airport convenience, family stay, quiet stay — only where this matches the real property location.',
    'Карточка слабо продаёт trust-triggers и обещание проживания':
      'The listing weakly sells trust triggers and the stay promise.',
    'Даже при хорошей локации карточка не даёт пользователю быстрых причин выбрать именно этот объект.':
      'Even with a good location, the listing does not give the user enough quick reasons to choose this property.',
    'Пользователь видит объект, но не получает достаточно поводов перейти к бронированию или прямому контакту.':
      'The user sees the property but does not get enough reasons to move to booking or direct contact.',
    'Для hotel-кейса критичны короткие обещания и подтверждения формата: breakfast, Wi-Fi, airport transfer, 24/7 reception, best price guarantee.':
      'For a hotel case, short promises and proof points are critical: breakfast, Wi-Fi, airport transfer, 24/7 reception, best price guarantee.',
    'Вынести реальные trust-triggers в описание, категории, ответы на отзывы и фото-подачу. Использовать только подтверждённые обещания, без маркетинговых преувеличений.':
      'Bring real trust triggers into the description, categories, review replies, and photo presentation. Use only confirmed promises without marketing exaggeration.',
    'У карточки нет сильного описания под сценарии локального поиска.':
      'The listing lacks a strong description tailored to local search scenarios.',
    'Падает конверсия из просмотра карточки в клик и бронь.':
      'Conversion from listing view to click and booking drops.',
    'Добавить описание 500–1000 символов: формат объекта, сильные стороны, локация, кому подходит, какие ожидания важно выставить заранее.':
      'Add a 500–1000 character description covering the property format, strengths, location, who it suits, and which expectations should be set in advance.',
    'Для hospitality алгоритмы и пользователи ждут регулярные posts, фото и обновления.':
      'For hospitality, both algorithms and users expect regular posts, photos, and updates.',
    'Снижается доверие, а карточка реже выигрывает по freshness и вовлечению.':
      'Trust drops, and the listing is less likely to win on freshness and engagement.',
    'Добавить регулярные posts: процедуры, nearby tips, family stay, quiet stay, airport convenience, spa journeys.':
      'Add regular posts: treatments, nearby tips, family stay, quiet stay, airport convenience, spa journeys.',
    'Не хватает: сайт.':
      'Missing: website.',
    'Переписать описание карточки: честно позиционировать объект, кому он подходит и какие преимущества получает гость.':
      'Rewrite the listing description: position the property honestly, explain who it suits, and what benefits the guest gets.',
    'Проверить категории и атрибуты: resort/apartments/spa/wellness/family-friendly/parking/pool/kitchen.':
      'Review categories and attributes: resort/apartments/spa/wellness/family-friendly/parking/pool/kitchen.',
    'Запустить регулярные posts/updates под сценарии поиска: quiet stay near city, family apartments, spa/wellness, airport nearby.':
      'Launch regular posts/updates for search scenarios: quiet stay near city, family apartments, spa/wellness, airport nearby.',
    'Отвечать на новые отзывы так, чтобы усиливать реальное позиционирование объекта.':
      'Reply to new reviews in a way that reinforces the property’s real positioning.',
    'Публиковать свежие фото и updates минимум 1–2 раза в неделю.':
      'Publish fresh photos and updates at least 1–2 times per week.',
    'Регулярно проверять, не расходится ли обещание карточки с фактическим опытом гостя.':
      'Regularly check that the listing promise matches the actual guest experience.',
    'Честно объяснить формат проживания и кому объект подходит лучше всего':
      'Clearly explain the stay format and who this property suits best.',
    'Убрать обещания, которые создают завышенное ожидание':
      'Remove promises that create inflated expectations.',
    'Упаковать сильные стороны из отзывов в описание и ответы на отзывы':
      'Turn the strongest review themes into the listing description and review replies.',
    'Добавить trust-triggers: free Wi-Fi, breakfast, airport transfer, 24/7 reception, best price guarantee — если они реально доступны':
      'Add trust triggers: free Wi-Fi, breakfast, airport transfer, 24/7 reception, best price guarantee — only if they are really available.',
    'Добавить описание 500–1000 символов: формат объекта, nearby landmarks, сильные стороны, локация, кому подходит и какие ожидания важно выставить заранее.':
      'Add a 500–1000 character description covering the property format, nearby landmarks, strengths, location, who it suits, and which expectations should be set in advance.',
    'Есть точки роста. Карточка уже имеет сильный social proof, но пока слабо управляет ожиданиями и позиционированием. Сильные стороны по отзывам: чистота, тихая локация, бассейн. Главная зона риска сейчас — ожидания гостей и слабая упаковка объекта под поисковые сценарии.':
      'There is room to grow. The listing already has strong social proof, but it still manages expectations and positioning weakly. The strongest review themes are cleanliness, quiet location, and pool. The main risk right now is guest expectations and weak packaging for search scenarios.',
    'Нужны конкретные точки входа, чтобы карточка отвечала на поисковый запрос.':
      'The listing needs concrete entry points so it can answer real search intent.',
    'Понятный формат услуги с диапазоном цены':
      'A clear service format with a price range.',
    'Собрать trust-triggers и вынести их в карточку и описание: breakfast, free Wi-Fi, airport transfer, 24/7 reception, best price guarantee — только если это реально доступно.':
      'Gather trust triggers and bring them into the listing and description: breakfast, free Wi-Fi, airport transfer, 24/7 reception, best price guarantee — only if these are truly available.',
    'Убрать booking-offers из блока услуг и заменить их на реальные единицы предложения: stay format, amenities, wellness/spa services или room types.':
      'Remove booking offers from the service block and replace them with real offer units: stay format, amenities, wellness/spa services, or room types.',
    'семейный формат': 'family-friendly format',
    'кухня': 'kitchen',
    'чистота': 'cleanliness',
  },
  el: {
    'Есть точки роста': 'Υπάρχουν σημεία ανάπτυξης',
    'Сильная карточка': 'Ισχυρή καταχώριση',
    'Карточка теряет клиентов': 'Η καταχώριση χάνει πελάτες',
    'Готовим отчёт': 'Ετοιμάζουμε την αναφορά',
    'Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.':
      'Αναλύουμε ήδη την καταχώριση και συλλέγουμε δεδομένα. Συνήθως αυτό διαρκεί 1–3 λεπτά.',
    'Отчёт готовится дольше обычного. Мы продолжаем обработку данных.':
      'Η αναφορά παίρνει περισσότερο χρόνο από το συνηθισμένο. Συνεχίζουμε την επεξεργασία των δεδομένων.',
    'Нет структуры услуг': 'Δεν υπάρχει δομή υπηρεσιών',
    'Нет актуальных фото': 'Δεν υπάρχουν πρόσφατες φωτογραφίες',
    'Карточка выглядит неактивной': 'Η καταχώριση φαίνεται ανενεργή',
    'В карточке не видно активного списка услуг.': 'Δεν εμφανίζεται ενεργή λίστα υπηρεσιών στην καταχώριση.',
    'В карточке не видно визуального подтверждения качества.': 'Δεν υπάρχει οπτική απόδειξη ποιότητας στην καταχώριση.',
    'Нет регулярных признаков ведения карточки.': 'Δεν υπάρχουν τακτικά σημάδια ενεργής διαχείρισης της καταχώρισης.',
    'Добавить ключевые услуги с категориями, описаниями и ценами.':
      'Προσθέστε βασικές υπηρεσίες με κατηγορίες, περιγραφές και τιμές.',
    'Добавить свежие фото работ, команды или интерьера.':
      'Προσθέστε πρόσφατες φωτογραφίες έργων, ομάδας ή εσωτερικού χώρου.',
    'Публиковать не менее 4 обновлений в месяц и добавлять новые фото.':
      'Δημοσιεύστε τουλάχιστον 4 ενημερώσεις τον μήνα και προσθέτετε νέες φωτογραφίες.',
    'За 24 часа': 'Μέσα σε 24 ώρες',
    'За 7 дней': 'Μέσα σε 7 ημέρες',
    'На постоянной основе': 'Σε συνεχή βάση',
    'Публиковать новости/обновления минимум 4 раз(а) в месяц.':
      'Δημοσιεύστε νέα και ενημερώσεις τουλάχιστον 4 φορές τον μήνα.',
    'Добавлять новые фото минимум 8 раз(а) в месяц.':
      'Προσθέστε νέες φωτογραφίες τουλάχιστον 8 φορές τον μήνα.',
    'Отвечать на отзывы не позднее 48 часов.':
      'Απαντάτε στις κριτικές μέσα σε 48 ώρες.',
    'Собираем фактические данные карточки': 'Συλλέγουμε τα πραγματικά δεδομένα της καταχώρισης',
    'Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.':
      'Αντλούμε υπηρεσίες, κριτικές, βαθμολογία, φωτογραφίες και στοιχεία επικοινωνίας από την καταχώριση χάρτη.',
    'Формируем персональный аудит': 'Δημιουργούμε εξατομικευμένο έλεγχο',
    'После парсинга покажем конкретные шаги роста именно для вашей карточки.':
      'Μετά την ανάλυση θα δείξουμε συγκεκριμένα βήματα ανάπτυξης ειδικά για τη δική σας καταχώριση.',
    'Аудит карточки на картах': 'Έλεγχος καταχώρισης στους χάρτες',
  },
  tr: {
    'Есть точки роста': 'Gelişim alanları var',
    'Сильная карточка': 'Güçlü profil',
    'Карточка теряет клиентов': 'Profil müşteri kaybediyor',
    'Готовим отчёт': 'Rapor hazırlanıyor',
    'Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.':
      'Profili analiz ediyor ve verileri topluyoruz. Bu işlem genelde 1–3 dakika sürer.',
    'Отчёт готовится дольше обычного. Мы продолжаем обработку данных.':
      'Rapor normalden uzun sürüyor. Verileri işlemeye devam ediyoruz.',
    'Нет структуры услуг': 'Hizmet yapısı yok',
    'Нет актуальных фото': 'Güncel fotoğraf yok',
    'Карточка выглядит неактивной': 'Profil pasif görünüyor',
    'В карточке не видно активного списка услуг.': 'Profildə aktif bir hizmet listesi görünmüyor.',
    'В карточке не видно визуального подтверждения качества.': 'Profilde kaliteyi gösteren görsel kanıt yok.',
    'Нет регулярных признаков ведения карточки.': 'Profilin düzenli yönetildiğine dair işaretler görünmüyor.',
    'Добавить ключевые услуги с категориями, описаниями и ценами.':
      'Temel hizmetleri kategori, açıklama ve fiyatlarla ekleyin.',
    'Добавить свежие фото работ, команды или интерьера.':
      'İşlerden, ekipten veya mekândan güncel fotoğraflar ekleyin.',
    'Публиковать не менее 4 обновлений в месяц и добавлять новые фото.':
      'Ayda en az 4 güncelleme yayınlayın ve yeni fotoğraflar ekleyin.',
    'За 24 часа': '24 saat içinde',
    'За 7 дней': '7 gün içinde',
    'На постоянной основе': 'Sürekli',
    'Публиковать новости/обновления минимум 4 раз(а) в месяц.':
      'Ayda en az 4 haber/güncelleme yayınlayın.',
    'Добавлять новые фото минимум 8 раз(а) в месяц.':
      'Ayda en az 8 yeni fotoğraf ekleyin.',
    'Отвечать на отзывы не позднее 48 часов.':
      'Yorumlara en geç 48 saat içinde yanıt verin.',
    'Собираем фактические данные карточки': 'Profilin gerçek verileri toplanıyor',
    'Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.':
      'Harita profilinden hizmetler, yorumlar, puan, fotoğraflar ve iletişim bilgileri çekiliyor.',
    'Формируем персональный аудит': 'Kişisel denetim hazırlanıyor',
    'После парсинга покажем конкретные шаги роста именно для вашей карточки.':
      'Analiz tamamlandıktan sonra profiliniz için özel büyüme adımlarını göstereceğiz.',
    'Аудит карточки на картах': 'Harita profili denetimi',
    'Гости, которые ищут спокойное размещение в Fatih':
      'Fatih bölgesinde sakin bir konaklama arayan misafirler.',
    'Гости, которые ищут спокойное размещение в Fethiye':
      'Fethiye bölgesinde sakin bir konaklama arayan misafirler.',
    'Семьи и пары, которым важны простор, бассейн и понятный формат отдыха':
      'Geniş alan, havuz ve net bir konaklama formatını önemseyen aileler ve çiftler.',
    'Путешественники, которым удобно передвигаться на машине':
      'Arabayla rahat hareket etmek isteyen gezginler.',
    'Те, кто ценит: кухня, чистота':
      'Şunlara önem veren misafirler: mutfak, temizlik.',
    'Те, кто ценит: cleanliness, тихая локация, бассейн':
      'Şunlara önem veren misafirler: temizlik, sakin konum, havuz.',
    'Гости, которые ожидают первую линию и мгновенный доступ к пляжу':
      'Denize sıfır konum ve plaja anında erişim bekleyen misafirler.',
    'Путешественники, которым важен формат классического hotel-by-the-sea':
      'Klasik deniz kenarı otel formatını önemseyen gezginler.',
    'Фасад и вход, чтобы объект было легко узнать':
      'Tesisi kolay tanımak için dış cephe ve giriş fotoğrafları.',
    'Фасад, вывеска и вход, чтобы объект было легко узнать на месте':
      'Tesisi yerinde kolay tanımak için dış cephe, tabela ve giriş fotoğrafları.',
    'Номера или апартаменты целиком: спальня, гостиная, кухня':
      'Oda veya dairenin tamamını gösteren kareler: yatak odası, salon, mutfak.',
    'Номера или апартаменты целиком: спальня, ванная, гостиная, kitchen':
      'Oda veya dairenin tamamını gösteren kareler: yatak odası, banyo, salon, mutfak.',
    'Номера или апартаменты целиком: спальня, ванная, гостиная, кухня':
      'Oda veya dairenin tamamını gösteren kareler: yatak odası, banyo, salon, mutfak.',
    'Бассейн, парковка и реальная окружающая инфраструктура':
      'Havuz, otopark ve çevredeki gerçek altyapı.',
    'Фото, которые честно показывают путь и расстояние до ключевых точек':
      'Önemli noktalara giden yolu ve gerçek mesafeyi dürüstçe gösteren fotoğraflar.',
    'Гостеприимство / размещение': 'Misafirperverlik / konaklama',
    'У объекта Oludenizevleri нет сильного описания под сценарии поиска по Fethiye.':
      'Oludenizevleri için Fethiye arama senaryolarına uygun güçlü bir açıklama yok.',
    'Описание не продаёт объект под поисковое намерение':
      'Açıklama, tesisi arama niyetine göre satmıyor.',
    'Карточка не объясняет, что это за формат отдыха и кому он подходит.':
      'Profil, konaklama formatının ne olduğunu ve kimler için uygun olduğunu açıklamıyor.',
    'Вместо услуг отображаются booking-offers или абстрактные позиции':
      'Gerçek hizmetler yerine booking-offers veya soyut öğeler gösteriliyor.',
    'Карточка не показывает реальное предложение объекта как SEO-единицы.':
      'Profil, tesisin gerçek teklifini SEO açısından anlamlı bir giriş noktası olarak göstermiyor.',
    'Карточка хуже ранжируется под сценарные запросы и слабее продаёт ценность объекта.':
      'Profil, niyet odaklı aramalarda daha kötü sıralanıyor ve tesisin değerini daha zayıf satıyor.',
    'Booking-offer позиций: 0. Реальных услуг/amenities: нет.':
      'Booking-offer sayısı: 0. Gerçek hizmet/olanak: yok.',
    'Показывать не агрегаторы бронирования, а реальное предложение: тип размещения, wellness/spa-процедуры, amenities, family-friendly features, parking, pool, kitchen.':
      'Rezervasyon toplayıcılarını değil, gerçek teklifi gösterin: konaklama tipi, wellness/spa hizmetleri, olanaklar, aile dostu özellikler, otopark, havuz, mutfak.',
    'Недостаточно сигналов активности':
      'Yeterli aktivite sinyali yok.',
    'Карточка не выглядит как живой активный объект.':
      'Profil, canlı ve aktif şekilde yönetilen bir tesis gibi görünmüyor.',
    'У карточки нет сильного описания под сценарии локального поиска.':
      'İşletme kartında yerel arama senaryolarına uygun güçlü bir açıklama yok.',
    'Падает конверсия из просмотра карточки в клик и бронь.':
      'Profil görüntülemeden tıklama ve rezervasyona geçiş dönüşümü düşüyor.',
    'Добавить описание 500–1000 символов: формат объекта, сильные стороны, локация, кому подходит, какие ожидания важно выставить заранее.':
      '500–1000 karakterlik bir açıklama ekleyin: tesis formatı, güçlü yönler, konum, kimler için uygun olduğu ve önceden hangi beklentilerin netleştirilmesi gerektiği.',
    'Для hospitality алгоритмы и пользователи ждут регулярные posts, фото и обновления.':
      'Hospitality kategorisinde hem algoritmalar hem de kullanıcılar düzenli gönderiler, fotoğraflar ve güncellemeler bekler.',
    'Снижается доверие, а карточка реже выигрывает по freshness и вовлечению.':
      'Güven azalır; profil güncellik ve etkileşim açısından daha az öne çıkar.',
    'Добавить регулярные posts: процедуры, nearby tips, family stay, quiet stay, airport convenience, spa journeys.':
      'Düzenli gönderiler ekleyin: deneyimler, nearby tips, family stay, quiet stay, airport convenience, spa journeys.',
    'Не хватает: сайт.':
      'Eksik olan: web sitesi.',
    'Переписать описание карточки: честно позиционировать объект, кому он подходит и какие преимущества получает гость.':
      'Profil açıklamasını yeniden yazın: tesisi dürüst biçimde konumlandırın, kimler için uygun olduğunu ve misafirin hangi avantajları elde ettiğini anlatın.',
    'Проверить категории и атрибуты: resort/apartments/spa/wellness/family-friendly/parking/pool/kitchen.':
      'Kategorileri ve nitelikleri kontrol edin: resort/apartments/spa/wellness/family-friendly/parking/pool/kitchen.',
    'Запустить регулярные posts/updates под сценарии поиска: quiet stay near city, family apartments, spa/wellness, airport nearby.':
      'Arama senaryolarına göre düzenli posts/updates başlatın: quiet stay near city, family apartments, spa/wellness, airport nearby.',
    'Отвечать на новые отзывы так, чтобы усиливать реальное позиционирование объекта.':
      'Yeni yorumlara, tesisin gerçek konumlandırmasını güçlendirecek şekilde yanıt verin.',
    'Публиковать свежие фото и updates минимум 1–2 раза в неделю.':
      'Haftada en az 1–2 kez yeni fotoğraflar ve güncellemeler yayınlayın.',
    'Регулярно проверять, не расходится ли обещание карточки с фактическим опытом гостя.':
      'Profilde verilen sözün gerçek misafir deneyimiyle çelişip çelişmediğini düzenli olarak kontrol edin.',
    'Ответа пока нет': 'Henüz yanıt yok',
    'Объём review engine ещё не даёт устойчивого преимущества':
      'Review engine hacmi henüz kalıcı bir avantaj sağlamıyor.',
    'Карточке не хватает свежих управляемых отзывов, чтобы перекрывать слабую репутацию и усиливать social proof.':
      'Zayıf itibarı dengelemek ve sosyal kanıtı güçlendirmek için profilde hâlâ yeterli taze ve yönetilen yorum yok.',
    'Репутация растёт медленно, а новый спрос дольше колеблется перед бронированием.':
      'İtibar yavaş büyüyor ve yeni talep rezervasyon öncesinde daha uzun süre tereddüt ediyor.',
    'Сейчас отзывов: 16. Для hotel-кейса этого ещё мало, чтобы уверенно выигрывать локальную конкуренцию при среднем рейтинге.':
      'Şu anda 16 yorum var. Bir otel senaryosu için bu sayı, orta düzey bir puanla yerel rekabette güvenle öne çıkmak için hâlâ yetersiz.',
    'Запустить сбор отзывов по сценарию после визита и просить конкретику про локацию, чистоту, сервис и удобство проживания.':
      'Konaklama sonrası yorum toplama akışını başlatın ve konum, temizlik, hizmet ve konfor hakkında somut detaylar isteyin.',
    'Категории, атрибуты и trust-triggers недораскрывают формат объекта':
      'Kategoriler, nitelikler ve trust-triggers tesis formatını tam açıklamıyor.',
    'Карточка не использует все сигналы, которые помогают туристу быстро понять уровень и формат проживания.':
      'Profil, gezginin konaklama düzeyini ve formatını hızla anlamasına yardımcı olan tüm sinyalleri kullanmıyor.',
    'Карточка теряет часть поисковых сценариев и хуже конвертирует холодный туристический трафик.':
      'Profil, bazı arama senaryolarını kaçırıyor ve soğuk turistik trafiği daha zayıf dönüştürüyor.',
    'Для hotel-кейсов особенно важны категории, nearby context и понятные promises: breakfast, Wi-Fi, airport transfer, family stay, 24/7 reception.':
      'Otel senaryolarında özellikle kategoriler, nearby context ve net promises önemlidir: breakfast, Wi-Fi, airport transfer, family stay, 24/7 reception.',
    'Проверить категории и атрибуты, а в тексте и карточке явно показать реальные trust-triggers, если они доступны.':
      'Kategorileri ve nitelikleri kontrol edin; gerçekten mevcutsa gerçek trust-triggers öğelerini metinde ve profilde açıkça gösterin.',
    'Карточка недоиспользует landmark и nearby-intent запросы':
      'Profil, landmark ve nearby-intent aramalarını yeterince kullanmıyor.',
    'Отель можно находить не только по названию, но и по сценариям рядом с ключевыми точками района.':
      'Otel yalnızca adıyla değil, bölgedeki önemli noktalara yakınlık senaryolarıyla da bulunabilir.',
    'Карточка недополучает трафик из туристических сценариев поиска и слабее конкурирует с более конкретно упакованными объектами.':
      'Profil, turistik arama senaryolarından trafik kaçırıyor ve daha net paketlenmiş tesislerle daha zayıf rekabet ediyor.',
    'Для hospitality в Fethiye важны nearby-intent формулировки: old city / landmark / airport / family stay / budget stay.':
      'Fethiye hospitality senaryosunda nearby-intent ifadeleri önemlidir: old city / landmark / airport / family stay / budget stay.',
    'Добавить в описание, posts и ответы на отзывы nearby-intent сценарии: near landmark, old city, airport convenience, family stay, quiet stay — только там, где это соответствует фактической локации объекта.':
      'Açıklamaya, posts ve yorum yanıtlarına nearby-intent senaryoları ekleyin: near landmark, old city, airport convenience, family stay, quiet stay — yalnızca tesisin gerçek konumuyla uyumluysa.',
    'Карточка слабо продаёт trust-triggers и обещание проживания':
      'Profil, trust-triggers ve konaklama vaadini zayıf satıyor.',
    'Даже при хорошей локации карточка не даёт пользователю быстрых причин выбрать именно этот объект.':
      'Konum iyi olsa bile profil, kullanıcıya bu tesisi seçmesi için yeterince hızlı neden sunmuyor.',
    'Пользователь видит объект, но не получает достаточно поводов перейти к бронированию или прямому контакту.':
      'Kullanıcı tesisi görüyor, ancak rezervasyona veya doğrudan iletişime geçmek için yeterli neden görmüyor.',
    'Для hotel-кейса критичны короткие обещания и подтверждения формата: breakfast, Wi-Fi, airport transfer, 24/7 reception, best price guarantee.':
      'Bir otel senaryosunda şu kısa vaatler ve kanıtlar kritiktir: breakfast, Wi‑Fi, airport transfer, 24/7 reception, best price guarantee.',
    'Вынести реальные trust-triggers в описание, категории, ответы на отзывы и фото-подачу. Использовать только подтверждённые обещания, без маркетинговых преувеличений.':
      'Gerçek trust-triggers öğelerini açıklamaya, kategorilere, yorum yanıtlarına ve fotoğraf sunumuna taşıyın. Yalnızca doğrulanmış vaatleri kullanın; pazarlama abartısından kaçının.',
    'Честно объяснить формат проживания и кому объект подходит лучше всего':
      'Konaklama formatını ve tesisin kimler için en uygun olduğunu açıkça anlatın.',
    'Убрать обещания, которые создают завышенное ожидание':
      'Aşırı beklenti yaratan vaatleri kaldırın.',
    'Упаковать сильные стороны из отзывов в описание и ответы на отзывы':
      'Yorumlardaki güçlü yanları açıklama ve yorum yanıtlarına taşıyın.',
    'Есть точки роста. Карточка уже имеет сильный social proof, но пока слабо управляет ожиданиями и позиционированием. Сильные стороны по отзывам: чистота, тихая локация, бассейн. Главная зона риска сейчас — ожидания гостей и слабая упаковка объекта под поисковые сценарии.':
      'Gelişim alanları var. Profilde zaten güçlü bir sosyal kanıt var, ancak beklentileri ve konumlandırmayı hâlâ zayıf yönetiyor. Yorumlardaki güçlü taraflar: temizlik, sakin konum ve havuz. Şu anda ana risk alanı misafir beklentileri ve tesisin arama senaryoları için zayıf paketlenmiş olması.',
    'Нужны конкретные точки входа, чтобы карточка отвечала на поисковый запрос.':
      'Profilin arama niyetine cevap verebilmesi için somut giriş noktalarına ihtiyaç var.',
    'Это повышает доверие и сокращает путь до первого обращения.':
      'Bu, güveni artırır ve ilk temasa giden yolu kısaltır.',
    'Понятный формат услуги с диапазоном цены':
      'Fiyat aralığı olan net bir hizmet formatı.',
    'Оценка ориентировочная и основана на модели карточки, а не на полном доступе к вашим продажам.':
      'Bu tahmin yön göstericidir ve kart modeline dayanır; satış verilerinize tam erişime değil.',
    'Локация и базовый social proof уже дают карточке потенциал, но главный bottleneck сейчас — репутация и review engine.':
      'Konum ve temel sosyal kanıt profile zaten potansiyel veriyor, ancak şu anda ana darboğaz itibar ve review engine.',
    'Главные зоны риска — рейтинг, ':
      'Ana risk alanları: puan, ',
    ' и слабая упаковка объекта под поисковые сценарии и landmarks.':
      ' ve tesisin arama senaryoları ile landmarks için zayıf şekilde paketlenmesi.',
    'Репутация карточки ниже порога доверия для отеля':
      'Profil itibarı otel için güven eşiğinin altında',
    'Низкий рейтинг становится главным bottleneck для видимости и бронирований.':
      'Düşük puan, görünürlük ve rezervasyonlar için ana darboğaz hâline geliyor.',
    'Для hotel-формата это уже влияет на выбор особенно сильно.':
      'Hotel formatında bu durum seçim kararını özellikle güçlü etkiler.',
    'Карточка хуже конвертирует в бронь и теряет часть показов по коммерческим сценариям.':
      'Profil rezervasyona daha kötü dönüşür ve ticari arama senaryolarında görünürlüğün bir kısmını kaybeder.',
    'Дожать review engine: QR после заселения/выезда, WhatsApp-напоминание и ответы на каждый новый отзыв.':
      'Review engine’i sıkılaştırın: check-in/check-out sonrası QR, WhatsApp hatırlatması ve her yeni yoruma yanıt.',
    'Отзывы есть, но ответы не дожимают доверие и видимость':
      'Yorumlar var, ancak yanıtlar güveni ve görünürlüğü yeterince güçlendirmiyor',
    'Карточка получает trust из отзывов, но не усиливает его регулярными ответами и управляемой рамкой.':
      'Profil yorumlardan güven kazanıyor, ancak bunu düzenli yanıtlar ve yönetilen bir çerçeve ile güçlendirmiyor.',
    'Потенциал social proof не превращается в бронь, карточка выглядит менее живой и слабее поддерживает локальную видимость.':
      'Sosyal kanıt potansiyeli rezervasyona dönüşmüyor; profil daha az canlı görünüyor ve yerel görünürlüğü daha zayıf destekliyor.',
    'Отвечать на отзывы с правильной рамкой: подчеркивать реальные сильные стороны, спокойно объяснять ограничения формата и поддерживать сигналы активности карточки.':
      'Yorumlara doğru çerçeveyle yanıt verin: gerçek güçlü yanları vurgulayın, format sınırlamalarını sakin biçimde açıklayın ve profilin aktivite sinyallerini destekleyin.',
    'Переписать описание карточки: добавить search-intents, nearby landmarks, честное позиционирование и кому объект подходит лучше всего.':
      'Profil açıklamasını yeniden yazın: search-intents, nearby landmarks, dürüst konumlandırma ve tesisin kimler için en uygun olduğunu ekleyin.',
    'Запустить review engine как главный рычаг роста: QR после заселения/выезда, напоминание в WhatsApp и ответы на все новые отзывы.':
      'Ana büyüme kaldıracı olarak review engine’i başlatın: check-in/check-out sonrası QR, WhatsApp hatırlatması ve tüm yeni yorumlara yanıt.',
    'Ответить на ключевые отзывы так, чтобы усилить доверие, поддержать видимость карточки и снять повторяющиеся возражения.':
      'Temel yorumlara güveni güçlendirecek, profil görünürlüğünü destekleyecek ve tekrar eden itirazları azaltacak şekilde yanıt verin.',
    'Собрать фото-историю объекта: фасад, вывеска, номера, завтраки, reception, парковка, вид из окна и what-you-really-get.':
      'Tesisin foto-hikâyesini toplayın: dış cephe, tabela, odalar, kahvaltı, reception, otopark, pencere manzarası ve what-you-really-get.',
    'Проверить категории и атрибуты: hotel / budget hotel / family hotel / breakfast / airport transfer / Wi-Fi / 24-7 reception — по факту доступных опций.':
      'Kategorileri ve nitelikleri kontrol edin: hotel / budget hotel / family hotel / breakfast / airport transfer / Wi-Fi / 24-7 reception — gerçekten sunulan seçeneklere göre.',
    'Запустить регулярные posts/updates под сценарии поиска: near landmark, budget stay, breakfast included, airport transfer, family stay.':
      'Arama senaryolarına göre düzenli posts/updates başlatın: near landmark, budget stay, breakfast included, airport transfer, family stay.',
    'Нарастить объём свежих отзывов по правильному сценарию: просить конкретику про локацию, чистоту, сервис и удобство проживания.':
      'Taze yorum hacmini doğru senaryoyla artırın: konum, temizlik, hizmet ve konfor hakkında somut detaylar isteyin.',
    'Отвечать на новые отзывы так, чтобы усиливать реальное позиционирование объекта, доверие и сигналы видимости карточки.':
      'Yeni yorumlara, tesisin gerçek konumlandırmasını, güveni ve profilin görünürlük sinyallerini güçlendirecek şekilde yanıt verin.',
    'Завтраки, зона reception, бассейн, парковка и реальные удобства объекта':
      'Kahvaltı, reception alanı, havuz, otopark ve tesisin gerçek olanakları.',
    'Фото вида из окна, ближайшей инфраструктуры и реального пути до ключевых точек':
      'Pencere manzarası, yakın çevre altyapısı ve önemli noktalara gerçek ulaşım yolunu gösteren fotoğraflar.',
    'Добавить trust-triggers: free Wi-Fi, breakfast, airport transfer, 24/7 reception, best price guarantee — если они реально доступны':
      'Gerçekten mevcutsa trust-triggers ekleyin: free Wi-Fi, breakfast, airport transfer, 24/7 reception, best price guarantee',
    'Добавить описание 500–1000 символов: формат объекта, nearby landmarks, сильные стороны, локация, кому подходит и какие ожидания важно выставить заранее.':
      '500–1000 karakterlik bir açıklama ekleyin: tesis formatı, nearby landmarks, güçlü yönler, konum, kimler için uygun olduğu ve önceden hangi beklentilerin netleştirilmesi gerektiği.',
    'Собрать trust-triggers и вынести их в карточку и описание: breakfast, free Wi-Fi, airport transfer, 24/7 reception, best price guarantee — только если это реально доступно.':
      'Trust-triggers öğelerini toplayıp karta ve açıklamaya taşıyın: breakfast, free Wi-Fi, airport transfer, 24/7 reception, best price guarantee — yalnızca gerçekten mevcutsa.',
    'Убрать booking-offers из блока услуг и заменить их на реальные единицы предложения: stay format, amenities, wellness/spa services или room types.':
      'Hizmet bloğundan booking-offers öğelerini kaldırın ve bunları gerçek teklif birimleriyle değiştirin: stay format, amenities, wellness/spa services veya room types.',
    'семейный формат': 'aile dostu format',
    'кухня': 'mutfak',
    'чистота': 'temizlik',
  },
  ar: {
    'Есть точки роста': 'هناك فرص واضحة للنمو',
    'Сильная карточка': 'بطاقة قوية',
    'Карточка теряет клиентов': 'البطاقة تخسر عملاء',
    'Готовим отчёт': 'نُعِد التقرير',
    'Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.':
      'نقوم الآن بتحليل البطاقة وجمع البيانات. يستغرق هذا عادة من دقيقة إلى ثلاث دقائق.',
    'Отчёт готовится дольше обычного. Мы продолжаем обработку данных.':
      'يستغرق التقرير وقتاً أطول من المعتاد. ما زلنا نواصل معالجة البيانات.',
    'Нет структуры услуг': 'لا توجد هيكلة واضحة للخدمات',
    'Нет актуальных фото': 'لا توجد صور حديثة',
    'Карточка выглядит неактивной': 'تبدو البطاقة غير نشطة',
    'В карточке не видно активного списка услуг.': 'لا تظهر قائمة خدمات نشطة في البطاقة.',
    'В карточке не видно визуального подтверждения качества.': 'لا يوجد دليل بصري واضح على الجودة في البطاقة.',
    'Нет регулярных признаков ведения карточки.': 'لا توجد مؤشرات منتظمة على أن البطاقة تُدار بشكل نشط.',
    'Добавить ключевые услуги с категориями, описаниями и ценами.':
      'أضف الخدمات الأساسية مع الفئات والأوصاف والأسعار.',
    'Добавить свежие фото работ, команды или интерьера.':
      'أضف صوراً حديثة للأعمال أو الفريق أو المكان.',
    'Публиковать не менее 4 обновлений в месяц и добавлять новые фото.':
      'انشر ما لا يقل عن 4 تحديثات شهرياً وأضف صوراً جديدة بانتظام.',
    'За 24 часа': 'خلال 24 ساعة',
    'За 7 дней': 'خلال 7 أيام',
    'На постоянной основе': 'بشكل مستمر',
    'Публиковать новости/обновления минимум 4 раз(а) в месяц.':
      'انشر الأخبار والتحديثات 4 مرات شهرياً على الأقل.',
    'Добавлять новые фото минимум 8 раз(а) в месяц.':
      'أضف صوراً جديدة 8 مرات شهرياً على الأقل.',
    'Отвечать на отзывы не позднее 48 часов.':
      'قم بالرد على المراجعات خلال 48 ساعة كحد أقصى.',
    'Добавить описание, которое объясняет бизнес как решение задачи: кто вы, кому помогаете, с чем к вам приходят и почему выбрать именно вас, а не соседнюю карточку.':
      'أضف وصفاً يشرح النشاط التجاري كحل واضح للمشكلة: من أنتم، ولمن تساعدون، وما الذي يأتي الناس إليكم من أجله، ولماذا ينبغي اختياركم أنتم لا البطاقة المجاورة.',
    'Собрать 5–10 ключевых услуг или товарных групп как отдельные точки входа в спрос, чтобы карточка перестала быть абстрактной визиткой.':
      'اجمع 5 إلى 10 خدمات أساسية أو مجموعات منتجات باعتبارها نقاط دخول مستقلة للطلب حتى لا تبقى البطاقة مجرد بطاقة تعريف عامة.',
    'Проверить категории, контакты и атрибуты, чтобы карточка соответствовала не общему профилю бизнеса, а конкретным коммерческим сценариям поиска.':
      'راجع الفئات ووسائل الاتصال والسمات بحيث تعكس البطاقة سيناريوهات البحث التجارية الفعلية، لا مجرد الملف العام للنشاط.',
    'Подготовить 3–5 updates, которые отвечают на реальный входящий спрос: кейсы, новые услуги, частые вопросы, сезонные предложения и рабочие процессы.':
      'حضّر 3 إلى 5 تحديثات تجيب عن الطلب الفعلي القادم: حالات عملية، خدمات جديدة، أسئلة شائعة، عروض موسمية، وشرح لطريقة العمل.',
    'Поддерживать актуальность услуг, цен, фото и контактов, чтобы карточка не расходилась с реальностью.':
      'حافظ على تحديث الخدمات والأسعار والصور وبيانات الاتصال حتى لا تنفصل البطاقة عن الواقع.',
    'Регулярно отвечать на отзывы и превращать их в понятный social proof, а не просто закрывать долг.':
      'رد بانتظام على المراجعات وحوّلها إلى دليل اجتماعي واضح بدلاً من مجرد إغلاق مهمة متأخرة.',
    'Держать карточку живой через кейсы, обновления и визуальные подтверждения реальной работы.':
      'أبقِ البطاقة حيّة عبر الحالات والتحديثات والأدلة البصرية على العمل الحقيقي.',
    'Для локального бизнеса важны регулярные фото, updates, ответы на отзывы и актуальные услуги.':
      'بالنسبة للنشاط المحلي، الصور المنتظمة والتحديثات والردود على المراجعات والخدمات المحدثة كلها مهمة.',
    'Добавить описание: кто вы, какие задачи решаете, в чём сильные стороны и что клиент получает на выходе.':
      'أضف وصفاً يوضح من أنتم، وما المشكلات التي تحلونها، وما نقاط القوة لديكم، وما الذي يحصل عليه العميل في النهاية.',
    'Есть точки роста. Карточка Knight Mobile Maintenance: рейтинг 4.8, отзывов 5, услуг 0. Сайт: нет, свежая активность: есть. Основной потенциал роста сейчас в структуре услуг.':
      'هناك فرص للنمو. بطاقة Knight Mobile Maintenance: التقييم 4.8، عدد المراجعات 5، عدد الخدمات 0. الموقع: لا، والنشاط الحديث: نعم. أكبر فرصة للنمو الآن هي في هيكلة الخدمات.',
    'Заполнить отсутствующие контакты и проверить кликабельность ссылок.':
      'أكمل بيانات التواصل الناقصة وتأكد من أن الروابط قابلة للنقر.',
    'Запустить сбор отзывов после визита и закрепить еженедельный ритм.':
      'ابدأ بجمع المراجعات بعد كل زيارة وثبّت إيقاعاً أسبوعياً لهذا العمل.',
    'Карточке не хватает сигналов активности':
      'البطاقة تفتقر إلى إشارات النشاط',
    'Клиенту сложно быстро понять, зачем сюда обращаться.':
      'يصعب على العميل أن يفهم بسرعة لماذا يجب أن يتواصل مع هذا النشاط.',
    'Описание карточки не объясняет ценность бизнеса':
      'وصف البطاقة لا يوضح قيمة النشاط التجاري',
    'Карточка не даёт понять, что это за бизнес, для кого он и с чем сюда обращаться.':
      'لا توضح البطاقة ما هو هذا النشاط التجاري، ولمن يناسب، وما الذي ينبغي أن يتواصل الناس بشأنه.',
    'Общее описание без структуры':
      'وصف عام بلا هيكلة',
    'Нет цены или формата':
      'لا يوجد سعر أو صيغة واضحة للخدمة',
    'Ключевая услуга с понятным названием':
      'خدمة أساسية باسم واضح',
    'Ключевые услуги или товарные группы':
      'الخدمات الأساسية أو مجموعات المنتجات',
    'Команда, рабочая зона и примеры результата':
      'الفريق، ومساحة العمل، وأمثلة على النتائج',
    'Локальный бизнес':
      'نشاط محلي',
    'Люди, которые ищут конкретную услугу рядом в вашем городе':
      'أشخاص يبحثون عن خدمة محددة بالقرب منهم في مدينتك',
    'Новый трафик, если карточка не объясняет формат услуги и её результат':
      'الزوار الجدد قد يغادرون إذا لم تشرح البطاقة صيغة الخدمة والنتيجة التي تقدمها.',
    'Новым клиентам сложнее доверять карточке.':
      'يصعب على العملاء الجدد الوثوق بالبطاقة.',
    'Объём social proof пока слабый.':
      'حجم الدليل الاجتماعي ما زال ضعيفاً.',
    'Оценка ориентировочная и основана на модели карточки, а не на полном доступе к вашим продажам.':
      'هذا التقدير تقريبي ويعتمد على نموذج البطاقة، وليس على وصول كامل إلى بيانات مبيعاتكم.',
    'Падает доверие и карточка хуже конвертирует в обращение.':
      'تنخفض الثقة وتتحول البطاقة بشكل أضعف إلى استفسارات.',
    'Пользователи, которым важны доверие, понятный прайс и удобный контакт':
      'المستخدمون الذين يهمهم الثقة، والأسعار الواضحة، وسهولة التواصل',
    'Превратить карточку из визитки в понятную точку входа в спрос':
      'حوّل البطاقة من مجرد بطاقة تعريف إلى نقطة دخول واضحة للطلب',
    'Публиковать обновления, кейсы, новости и новые фото на регулярной основе.':
      'انشر التحديثات ودراسات الحالة والأخبار والصور الجديدة بشكل منتظم.',
    'Сейчас отзывов: 5, ориентир: 30+.':
      'عدد المراجعات الآن: 5، والهدف: 30+.',
    'Сейчас услуг: 0.':
      'عدد الخدمات الآن: 0.',
    'Снижается freshness, доверие и вероятность обращения.':
      'تنخفض حداثة البطاقة والثقة واحتمال التواصل.',
    'Собрать ключевые услуги или категории предложения как отдельные, понятные и коммерчески полезные позиции.':
      'اجمع الخدمات الأساسية أو فئات العرض كعناصر منفصلة وواضحة وذات قيمة تجارية.',
    'У Knight Mobile Maintenance нет сильного описания под локальный спрос в .':
      'لا تملك Knight Mobile Maintenance حالياً وصفاً قوياً موجهاً للطلب المحلي في منطقتها.',
    'Усилить доверие через контакты, фото и конкретику по услугам':
      'عزّز الثقة عبر بيانات التواصل والصور والتفاصيل الواضحة للخدمات',
    'Фасад или вход, чтобы бизнес было легко найти':
      'صورة للواجهة أو المدخل حتى يسهل العثور على النشاط',
    'Часть потенциальных клиентов не доходит до контакта.':
      'بعض العملاء المحتملين لا يصلون إلى مرحلة التواصل.',
    'Это повышает доверие и сокращает путь до первого обращения.':
      'هذا يزيد الثقة ويقلّص الطريق إلى أول تواصل.',
    'конкретная услуга + вашем городе':
      'خدمة محددة + مدينتك',
    'магазин': 'متجر',
    'услуга рядом вашем городе':
      'خدمة قريبة في مدينتك',
    'цена / отзывы / запись вашем городе':
      'السعر / المراجعات / الحجز في مدينتك',
    'Собираем фактические данные карточки': 'نجمع البيانات الفعلية للبطاقة',
    'Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.':
      'نقوم بجلب الخدمات والمراجعات والتقييمات والصور وبيانات الاتصال من بطاقة الخرائط.',
    'Формируем персональный аудит': 'نبني تدقيقاً مخصصاً',
    'После парсинга покажем конкретные шаги роста именно для вашей карточки.':
      'بعد اكتمال التحليل سنعرض خطوات نمو محددة لبطاقتك أنت بالذات.',
    'Аудит карточки на картах': 'تدقيق بطاقة الخرائط',
    'Ответа пока нет': 'لا يوجد رد حتى الآن',
  },
};

const resolveTranslationLang = (lang: PageLang) => (AUDIT_TEXT_TRANSLATIONS[lang] ? lang : 'en');

const translateHospitalityTheme = (lang: PageLang, value: string): string => {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return value.trim();
  const mapEn: Record<string, string> = {
    'кухня': 'kitchen',
    'чистота': 'cleanliness',
    'тихая локация': 'quiet location',
    'бассейн': 'pool',
  };
  const mapTr: Record<string, string> = {
    'кухня': 'mutfak',
    'чистота': 'temizlik',
    'тихая локация': 'sakin konum',
    'бассейн': 'havuz',
  };
  const mapAr: Record<string, string> = {
    'кухня': 'مطبخ',
    'чистота': 'النظافة',
    'тихая локация': 'موقع هادئ',
    'бассейн': 'مسبح',
  };
  const mapEl: Record<string, string> = {
    'кухня': 'κουζίνα',
    'чистота': 'καθαριότητα',
    'тихая локация': 'ήσυχη τοποθεσία',
    'бассейн': 'πισίνα',
  };
  const mapByLang: Record<string, Record<string, string>> = {
    en: mapEn,
    tr: mapTr,
    ar: mapAr,
    el: mapEl,
  };
  return mapByLang[lang]?.[normalized] || value.trim();
};

const translateAuditText = (lang: PageLang, value?: string | null): string => {
  const source = String(value || '').trim();
  if (!source || lang === 'ru') return source;
  const dict = AUDIT_TEXT_TRANSLATIONS[resolveTranslationLang(lang)];
  if (!dict) return source;

  const bestFitPrefix = 'Гости, которые ищут спокойное размещение в ';
  if (source.startsWith(bestFitPrefix)) {
    const city = source.slice(bestFitPrefix.length).trim();
    if (lang === 'en') return `Guests looking for a calm stay in ${city}`;
    if (lang === 'tr') return `${city} bölgesinde sakin bir konaklama arayan misafirler`;
    if (lang === 'ar') return `ضيوف يبحثون عن إقامة هادئة في ${city}`;
    if (lang === 'el') return `Επισκέπτες που αναζητούν ήρεμη διαμονή στο ${city}`;
  }
  const carePrefix = 'Те, кто ценит: ';
  if (source.startsWith(carePrefix)) {
    const themes = source
      .slice(carePrefix.length)
      .split(',')
      .map((item) => translateHospitalityTheme(lang, item))
      .filter(Boolean);
    const joined = themes.join(', ');
    if (lang === 'en') return `Guests who care about: ${joined}`;
    if (lang === 'tr') return `Şunlara önem veren misafirler: ${joined}`;
    if (lang === 'ar') return `الضيوف الذين يهتمون بـ: ${joined}`;
    if (lang === 'el') return `Επισκέπτες που δίνουν σημασία σε: ${joined}`;
  }

  let result = dict[source] || source;
  if (result === source) {
    Object.entries(dict).forEach(([from, to]) => {
      if (result.includes(from)) result = result.replaceAll(from, to);
    });
  }
  return result;
};

const AUDIT_HEALTH_LABELS = {
  ru: {
    strong: 'Сильная карточка',
    growth: 'Есть точки роста',
    risk: 'Карточка теряет клиентов',
  },
  en: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
  el: {
    strong: 'Ισχυρή καταχώριση',
    growth: 'Υπάρχουν σημεία ανάπτυξης',
    risk: 'Η καταχώριση χάνει πελάτες',
  },
  tr: {
    strong: 'Güçlü profil',
    growth: 'Gelişim alanları var',
    risk: 'Profil müşteri kaybediyor',
  },
  ar: {
    strong: 'بطاقة قوية',
    growth: 'هناك فرص واضحة للنمو',
    risk: 'البطاقة تخسر عملاء',
  },
  fr: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
  es: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
  de: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
  th: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
  ha: {
    strong: 'Strong listing',
    growth: 'There is room to grow',
    risk: 'The listing is losing customers',
  },
};

const ISSUE_TRANSLATIONS: Record<'en' | 'el' | 'tr' | 'ar', Record<string, { title: string; problem: string; impact: string; fix: string }>> = {
  en: {
    positioning_description_gap: {
      title: 'The description does not sell the property for search intent',
      problem: 'The listing does not explain the stay format or who it suits best.',
      impact: 'Conversion from listing view to click and booking drops.',
      fix: 'Add a 500–1000 character description covering the property format, strengths, location, who it suits, and which expectations should be set in advance.',
    },
    activity_signals_gap: {
      title: 'Not enough activity signals',
      problem: 'The listing does not look like a live, actively managed property.',
      impact: 'Trust drops, and the listing is less likely to win on freshness and engagement.',
      fix: 'Add regular posts: treatments, nearby tips, family stay, quiet stay, airport convenience, spa journeys.',
    },
    services_missing: {
      title: 'No service structure',
      problem: 'No active service list is visible in the listing.',
      impact: 'Visitors struggle to understand the offer, so inquiry conversion drops.',
      fix: 'Add core services with categories, descriptions, and prices.',
    },
    photo_story_gap: {
      title: 'Photos exist but do not work as a trust-building catalog',
      problem: 'The listing does not clearly show the result, the process, and what the customer will receive.',
      impact: 'Photos do not strengthen SEO, trust, or conversion from view to inquiry.',
      fix: 'Rebuild the visual layer into clear series: category examples, process shots, fittings, team, and finished results.',
    },
    services_short_list: {
      title: 'Service list is too short',
      problem: 'The service list looks incomplete.',
      impact: 'The listing gets fewer relevant impressions and fewer commercial clicks.',
      fix: 'Expand the priority service list and group it into clear categories.',
    },
    services_no_price: {
      title: 'Services without prices',
      problem: 'Most services do not show a price.',
      impact: 'Trust drops and decision-making becomes slower.',
      fix: 'Add prices at least for the core services.',
    },
    profile_contacts_gap: {
      title: 'Profile contacts are incomplete',
      problem: 'Not all contact channels are available in the listing.',
      impact: 'Some potential customers drop off before making contact.',
      fix: 'Fill in the missing contacts and verify that links are clickable.',
    },
    rating_gap: {
      title: 'Rating is below the target zone',
      problem: 'The listing rating is still below the stable trust level.',
      impact: 'Listing visibility and inbound conversion are lower.',
      fix: 'Collect fresh reviews and handle negative feedback with proper replies.',
    },
    reviews_low_count: {
      title: 'Not enough reviews',
      problem: 'The amount of social proof is still weak.',
      impact: 'New customers find it harder to trust the listing.',
      fix: 'Ask for reviews after each visit and establish a weekly collection rhythm.',
    },
    reviews_marketing_underused: {
      title: 'Reviews are underused as a trust layer',
      problem: 'The listing is not turning reviews into managed social proof.',
      impact: 'Trust exists, but it works weaker than it could.',
      fix: 'Reply to reviews in a way that reinforces quality, service, and real customer outcomes.',
    },
    reviews_unanswered: {
      title: 'There are unanswered reviews',
      problem: 'Some reviews are still waiting for a business response.',
      impact: 'Trust decreases and the chance of repeat contact gets lower.',
      fix: 'Close the review backlog and reply within the expected SLA.',
    },
    visual_no_photos: {
      title: 'Recent photos are missing',
      problem: 'The listing lacks visual proof of quality.',
      impact: 'Trust and click-through to contact both decrease.',
      fix: 'Add fresh photos of your work, team, or interior.',
    },
    activity_low: {
      title: 'The listing looks inactive',
      problem: 'There are no regular signs that the listing is being maintained.',
      impact: 'The listing attracts less attention and appears less often in priority placements.',
      fix: 'Publish regular updates and add fresh photos every month.',
    },
  },
  el: {
    services_missing: {
      title: 'Δεν υπάρχει δομή υπηρεσιών',
      problem: 'Δεν εμφανίζεται ενεργή λίστα υπηρεσιών στην καταχώριση.',
      impact: 'Οι επισκέπτες δυσκολεύονται να καταλάβουν την προσφορά και μειώνονται τα αιτήματα.',
      fix: 'Προσθέστε βασικές υπηρεσίες με κατηγορίες, περιγραφές και τιμές.',
    },
    services_short_list: {
      title: 'Η λίστα υπηρεσιών είναι πολύ μικρή',
      problem: 'Η λίστα υπηρεσιών φαίνεται ελλιπής.',
      impact: 'Η καταχώριση λαμβάνει λιγότερες σχετικές εμφανίσεις και λιγότερα εμπορικά κλικ.',
      fix: 'Επεκτείνετε τη βασική λίστα υπηρεσιών και οργανώστε την σε σαφείς κατηγορίες.',
    },
    services_no_price: {
      title: 'Υπηρεσίες χωρίς τιμές',
      problem: 'Οι περισσότερες υπηρεσίες δεν έχουν τιμή.',
      impact: 'Μειώνεται η εμπιστοσύνη και καθυστερεί η απόφαση.',
      fix: 'Προσθέστε τιμές τουλάχιστον στις βασικές υπηρεσίες.',
    },
    profile_contacts_gap: {
      title: 'Τα στοιχεία επικοινωνίας είναι ελλιπή',
      problem: 'Δεν είναι διαθέσιμα όλα τα κανάλια επικοινωνίας στην καταχώριση.',
      impact: 'Μέρος των πιθανών πελατών χάνεται πριν από την πρώτη επαφή.',
      fix: 'Συμπληρώστε τα στοιχεία που λείπουν και ελέγξτε ότι οι σύνδεσμοι λειτουργούν.',
    },
    rating_gap: {
      title: 'Η βαθμολογία είναι κάτω από τον στόχο',
      problem: 'Η βαθμολογία της καταχώρισης παραμένει κάτω από το επίπεδο σταθερής εμπιστοσύνης.',
      impact: 'Μειώνονται η προβολή της καταχώρισης και η μετατροπή σε εισερχόμενα αιτήματα.',
      fix: 'Συλλέξτε νέες κριτικές και διαχειριστείτε σωστά τα αρνητικά σχόλια.',
    },
    reviews_low_count: {
      title: 'Δεν υπάρχουν αρκετές κριτικές',
      problem: 'Η κοινωνική απόδειξη της καταχώρισης παραμένει αδύναμη.',
      impact: 'Οι νέοι πελάτες δυσκολεύονται περισσότερο να εμπιστευτούν την επιχείρηση.',
      fix: 'Ζητάτε κριτικές μετά από κάθε επίσκεψη και καθιερώστε εβδομαδιαίο ρυθμό συλλογής.',
    },
    reviews_unanswered: {
      title: 'Υπάρχουν κριτικές χωρίς απάντηση',
      problem: 'Μερικές κριτικές παραμένουν χωρίς απάντηση από την επιχείρηση.',
      impact: 'Μειώνεται η εμπιστοσύνη και η πιθανότητα επαναλαμβανόμενης επαφής.',
      fix: 'Κλείστε το backlog των κριτικών και απαντάτε εντός του αναμενόμενου SLA.',
    },
    visual_no_photos: {
      title: 'Λείπουν πρόσφατες φωτογραφίες',
      problem: 'Η καταχώριση δεν διαθέτει οπτική απόδειξη ποιότητας.',
      impact: 'Μειώνεται η εμπιστοσύνη και η πρόθεση επικοινωνίας.',
      fix: 'Προσθέστε πρόσφατες φωτογραφίες έργων, ομάδας ή εσωτερικού χώρου.',
    },
    activity_low: {
      title: 'Η καταχώριση φαίνεται ανενεργή',
      problem: 'Δεν υπάρχουν τακτικά σημάδια ενεργής διαχείρισης της καταχώρισης.',
      impact: 'Η καταχώριση τραβά λιγότερη προσοχή και εμφανίζεται λιγότερο συχνά σε προτεραιότητα.',
      fix: 'Δημοσιεύετε τακτικές ενημερώσεις και προσθέτετε νέες φωτογραφίες κάθε μήνα.',
    },
  },
  tr: {
    positioning_description_gap: {
      title: 'Açıklama, tesisi arama niyetine göre satmıyor',
      problem: 'Profil, konaklama formatının ne olduğunu ve kimler için uygun olduğunu açıklamıyor.',
      impact: 'Profil görüntülemeden tıklama ve rezervasyona geçiş dönüşümü düşüyor.',
      fix: '500–1000 karakterlik bir açıklama ekleyin: tesis formatı, güçlü yönler, konum, kimler için uygun olduğu ve önceden hangi beklentilerin netleştirilmesi gerektiği.',
    },
    activity_signals_gap: {
      title: 'Yeterli aktivite sinyali yok',
      problem: 'Profil, canlı ve aktif şekilde yönetilen bir tesis gibi görünmüyor.',
      impact: 'Güven azalır; profil güncellik ve etkileşim açısından daha az öne çıkar.',
      fix: 'Düzenli gönderiler ekleyin: deneyimler, nearby tips, family stay, quiet stay, airport convenience, spa journeys.',
    },
    services_missing: {
      title: 'Hizmet yapısı yok',
      problem: 'Profildə aktif bir hizmet listesi görünmüyor.',
      impact: 'Ziyaretçiler teklifi anlamakta zorlanır ve başvuru dönüşümü düşer.',
      fix: 'Temel hizmetleri kategori, açıklama ve fiyatlarla ekleyin.',
    },
    photo_story_gap: {
      title: 'Fotoğraflar var ama güven oluşturan bir katalog gibi çalışmıyor',
      problem: 'Profil sonuçları, süreci ve müşterinin ne alacağını net göstermiyor.',
      impact: 'Fotoğraflar SEO, güven ve başvuru dönüşümünü yeterince güçlendirmiyor.',
      fix: 'Görsel katmanı net serilere ayırın: kategori örnekleri, süreç fotoğrafları, prova/fitting, ekip ve bitmiş işler.',
    },
    services_short_list: {
      title: 'Hizmet listesi çok kısa',
      problem: 'Hizmet listesi eksik görünüyor.',
      impact: 'Profil daha az alakalı gösterim ve daha az ticari tıklama alır.',
      fix: 'Öncelikli hizmet listesini genişletin ve net kategorilere ayırın.',
    },
    services_no_price: {
      title: 'Fiyatsız hizmetler',
      problem: 'Çoğu hizmette fiyat görünmüyor.',
      impact: 'Güven azalır ve karar verme süresi uzar.',
      fix: 'En azından ana hizmetler için fiyat ekleyin.',
    },
    profile_contacts_gap: {
      title: 'İletişim bilgileri eksik',
      problem: 'Profilde tüm iletişim kanalları görünmüyor.',
      impact: 'Bazı potansiyel müşteriler iletişime geçmeden kaybolur.',
      fix: 'Eksik iletişim alanlarını doldurun ve bağlantıların çalıştığını doğrulayın.',
    },
    rating_gap: {
      title: 'Puan hedef seviyenin altında',
      problem: 'Profil puanı güven için hedeflenen seviyenin altında.',
      impact: 'Görünürlük ve inbound dönüşüm daha düşük olur.',
      fix: 'Yeni yorumlar toplayın ve olumsuz geri bildirimlere doğru yanıt verin.',
    },
    reviews_low_count: {
      title: 'Yorum sayısı yetersiz',
      problem: 'Sosyal kanıt hâlâ zayıf.',
      impact: 'Yeni müşterilerin profile güvenmesi zorlaşır.',
      fix: 'Her ziyaret sonrası yorum isteyin ve haftalık toplama ritmi kurun.',
    },
    reviews_marketing_underused: {
      title: 'Yorumlar güven katmanı olarak yeterince kullanılmıyor',
      problem: 'Profil yorumları yönetilen bir sosyal kanıta dönüştürmüyor.',
      impact: 'Güven var ama olabileceğinden daha zayıf çalışıyor.',
      fix: 'Yorumlara kaliteyi, hizmeti ve gerçek müşteri sonucunu öne çıkaracak şekilde cevap verin.',
    },
    reviews_unanswered: {
      title: 'Yanıtlanmamış yorumlar var',
      problem: 'Bazı yorumlar işletme yanıtı bekliyor.',
      impact: 'Güven zayıflar, profil daha az canlı görünür ve yerel görünürlük sinyalleri güç kaybeder.',
      fix: 'Yorum birikimini kapatın; yanıtları güveni destekleyen ve profilin görünürlüğünü artıran düzenli bir çalışma standardına dönüştürün.',
    },
    visual_no_photos: {
      title: 'Güncel fotoğraflar eksik',
      problem: 'Profilde kaliteyi gösteren görsel kanıt yok.',
      impact: 'Güven ve iletişime geçme isteği birlikte düşer.',
      fix: 'İşlerden, ekipten veya mekândan güncel fotoğraflar ekleyin.',
    },
    activity_low: {
      title: 'Profil pasif görünüyor',
      problem: 'Profilin düzenli yönetildiğine dair işaretler yok.',
      impact: 'Profil daha az dikkat çeker ve öncelikli alanlarda daha seyrek görünür.',
      fix: 'Düzenli güncellemeler yayınlayın ve her ay yeni fotoğraflar ekleyin.',
    },
  },
  ar: {
    positioning_description_gap: {
      title: 'وصف البطاقة لا يوضح قيمة النشاط التجاري',
      problem: 'لا توضح البطاقة ما هو هذا النشاط التجاري، ولمن يناسب، وما الذي ينبغي أن يتواصل الناس بشأنه.',
      impact: 'تنخفض الثقة وتتحول البطاقة بشكل أضعف إلى استفسارات.',
      fix: 'أضف وصفاً يوضح من أنتم، وما المشكلات التي تحلونها، وما نقاط القوة لديكم، وما الذي يحصل عليه العميل في النهاية.',
    },
    activity_signals_gap: {
      title: 'البطاقة تفتقر إلى إشارات النشاط',
      problem: 'لا توجد تحديثات كافية تجعل البطاقة تبدو حيّة وحديثة الإدارة.',
      impact: 'تنخفض الحداثة والثقة واحتمال التواصل.',
      fix: 'انشر تحديثات وقصص عمل وأخباراً وصوراً جديدة بشكل منتظم.',
    },
    services_missing: {
      title: 'لا توجد هيكلة واضحة للخدمات',
      problem: 'لا تظهر قائمة خدمات نشطة في البطاقة.',
      impact: 'يصعب على الزائر فهم العرض، لذلك تنخفض التحويلات إلى الاستفسار.',
      fix: 'أضف الخدمات الأساسية مع الفئات والأوصاف والأسعار.',
    },
    services_short_list: {
      title: 'قائمة الخدمات قصيرة جداً',
      problem: 'تبدو قائمة الخدمات غير مكتملة.',
      impact: 'تحصل البطاقة على ظهور أقل في النتائج ذات الصلة ونقرات تجارية أقل.',
      fix: 'وسّع قائمة الخدمات ذات الأولوية ونظّمها ضمن فئات واضحة.',
    },
    services_no_price: {
      title: 'خدمات بلا أسعار',
      problem: 'معظم الخدمات لا تعرض سعراً.',
      impact: 'تنخفض الثقة ويصبح اتخاذ القرار أبطأ.',
      fix: 'أضف الأسعار على الأقل للخدمات الأساسية.',
    },
    profile_contacts_gap: {
      title: 'بيانات الاتصال غير مكتملة',
      problem: 'ليست كل قنوات التواصل متاحة في البطاقة.',
      impact: 'بعض العملاء المحتملين يتسربون قبل أول تواصل.',
      fix: 'أكمل وسائل الاتصال الناقصة وتأكد من أن الروابط تعمل.',
    },
    rating_gap: {
      title: 'التقييم أقل من المنطقة المستهدفة',
      problem: 'تقييم البطاقة ما زال أقل من مستوى الثقة المستقر.',
      impact: 'تكون الرؤية والتحويلات الواردة أضعف.',
      fix: 'اجمع مراجعات جديدة وتعامل مع التعليقات السلبية بردود صحيحة.',
    },
    reviews_low_count: {
      title: 'عدد المراجعات غير كافٍ',
      problem: 'الدليل الاجتماعي ما زال ضعيفاً.',
      impact: 'يصعب على العملاء الجدد الوثوق بالبطاقة.',
      fix: 'اطلب مراجعات بعد كل زيارة وضع إيقاعاً أسبوعياً لجمعها.',
    },
    reviews_unanswered: {
      title: 'توجد مراجعات بلا رد',
      problem: 'بعض المراجعات ما زالت بانتظار رد من النشاط التجاري.',
      impact: 'تنخفض الثقة وتقل فرصة التواصل المتكرر.',
      fix: 'أغلق تراكم المراجعات والتزم بالرد ضمن الزمن المتوقع.',
    },
    visual_no_photos: {
      title: 'الصور الحديثة مفقودة',
      problem: 'البطاقة تفتقد إلى دليل بصري على الجودة.',
      impact: 'تنخفض الثقة ونية التواصل معاً.',
      fix: 'أضف صوراً حديثة للأعمال أو الفريق أو المكان.',
    },
    activity_low: {
      title: 'تبدو البطاقة غير نشطة',
      problem: 'لا توجد مؤشرات منتظمة على أن البطاقة تُدار باستمرار.',
      impact: 'تجذب البطاقة اهتماماً أقل وتظهر بوتيرة أقل في المواضع المميزة.',
      fix: 'انشر تحديثات منتظمة وأضف صوراً جديدة كل شهر.',
    },
  },
};

const localizedHealthLabel = (
  lang: PageLang,
  healthLevel?: string | null,
  healthLabel?: string | null,
): string => {
  if (lang === 'ru') return String(healthLabel || '').trim();
  const safeLevel = String(healthLevel || '').trim().toLowerCase();
  if (safeLevel === 'strong' || safeLevel === 'growth' || safeLevel === 'risk') {
    const labelMap = AUDIT_HEALTH_LABELS[lang] || AUDIT_HEALTH_LABELS.en;
    return labelMap[safeLevel];
  }
  return translateAuditText(lang, healthLabel);
};

const buildLocalizedEvidence = (
  lang: PageLang,
  issueId: string,
  issue: OfferPagePayload['audit']['issue_blocks'][number],
  state: NonNullable<OfferPagePayload['audit']>['current_state'],
) => {
  if (lang === 'ru') return String(issue?.evidence || '').trim();
  const servicesCount = Number(state?.services_count || 0);
  const pricedServicesCount = Number(state?.services_with_price_count || 0);
  const reviewsCount = Number(state?.reviews_count || 0);
  const unansweredReviewsCount = Number(state?.unanswered_reviews_count || 0);
  const rating = state?.rating;
  const evidenceById: Record<string, string> = {
    positioning_description_gap:
      lang === 'en'
        ? 'The listing lacks a strong description tailored to local search scenarios.'
        : lang === 'tr'
          ? 'İşletme kartında yerel arama senaryolarına uygun güçlü bir açıklama yok.'
          : lang === 'ar'
            ? 'لا توجد في البطاقة صياغة قوية مهيأة لسيناريوهات البحث المحلي.'
          : 'Η καταχώριση δεν διαθέτει ισχυρή περιγραφή προσαρμοσμένη στα τοπικά σενάρια αναζήτησης.',
    activity_signals_gap:
      lang === 'en'
        ? 'For hospitality, both algorithms and users expect regular posts, photos, and updates.'
        : lang === 'tr'
          ? 'Hospitality kategorisinde hem algoritmalar hem de kullanıcılar düzenli gönderiler, fotoğraflar ve güncellemeler bekler.'
          : lang === 'ar'
            ? 'في هذا النوع من البطاقات، تتوقع الخوارزميات والمستخدمون منشورات وصوراً وتحديثات منتظمة.'
          : 'Στη φιλοξενία, τόσο οι αλγόριθμοι όσο και οι χρήστες αναμένουν τακτικά posts, φωτογραφίες και ενημερώσεις.',
    services_missing:
      lang === 'en'
        ? `Services now: ${servicesCount}, with prices: ${pricedServicesCount}.`
        : lang === 'tr'
          ? `Mevcut hizmet: ${servicesCount}, fiyatlı hizmet: ${pricedServicesCount}.`
          : lang === 'ar'
            ? `الخدمات الحالية: ${servicesCount}، والخدمات التي تعرض سعراً: ${pricedServicesCount}.`
          : `Υπηρεσίες τώρα: ${servicesCount}, με τιμές: ${pricedServicesCount}.`,
    services_short_list:
      lang === 'en'
        ? `Services now: ${servicesCount}.`
        : lang === 'tr'
          ? `Mevcut hizmet sayısı: ${servicesCount}.`
          : lang === 'ar'
            ? `عدد الخدمات الحالية: ${servicesCount}.`
          : `Υπηρεσίες τώρα: ${servicesCount}.`,
    services_no_price:
      lang === 'en'
        ? `Priced services: ${pricedServicesCount} of ${servicesCount}.`
        : lang === 'tr'
          ? `Fiyatı görünen hizmet: ${pricedServicesCount}/${servicesCount}.`
          : lang === 'ar'
            ? `الخدمات ذات الأسعار: ${pricedServicesCount} من أصل ${servicesCount}.`
          : `Υπηρεσίες με τιμή: ${pricedServicesCount} από ${servicesCount}.`,
    rating_gap:
      lang === 'en'
        ? `Current rating: ${rating !== null && rating !== undefined ? Number(rating).toFixed(1) : 'n/a'}.`
        : lang === 'tr'
          ? `Mevcut puan: ${rating !== null && rating !== undefined ? Number(rating).toFixed(1) : 'yok'}.`
          : lang === 'ar'
            ? `التقييم الحالي: ${rating !== null && rating !== undefined ? Number(rating).toFixed(1) : 'غير متاح'}.`
          : `Τρέχουσα βαθμολογία: ${rating !== null && rating !== undefined ? Number(rating).toFixed(1) : 'n/a'}.`,
    reviews_low_count:
      lang === 'en'
        ? `Reviews now: ${reviewsCount}.`
        : lang === 'tr'
          ? `Mevcut yorum sayısı: ${reviewsCount}.`
          : lang === 'ar'
            ? `عدد المراجعات الحالي: ${reviewsCount}.`
          : `Κριτικές τώρα: ${reviewsCount}.`,
    reviews_unanswered:
      lang === 'en'
        ? `Unanswered reviews: ${unansweredReviewsCount}.`
        : lang === 'tr'
          ? `Yanıtlanmamış yorum: ${unansweredReviewsCount}.`
          : lang === 'ar'
            ? `المراجعات غير المُجاب عنها: ${unansweredReviewsCount}.`
          : `Κριτικές χωρίς απάντηση: ${unansweredReviewsCount}.`,
    visual_no_photos:
      lang === 'en'
        ? 'Recent visual proof is not visible in the listing.'
        : lang === 'tr'
          ? 'Profildə yakın döneme ait görsel kanıt görünmüyor.'
          : lang === 'ar'
            ? 'لا يظهر في البطاقة دليل بصري حديث وواضح.'
          : 'Δεν φαίνεται πρόσφατο οπτικό υλικό στην καταχώριση.',
    activity_low:
      lang === 'en'
        ? 'There are no visible recent updates in the listing.'
        : lang === 'tr'
          ? 'Profildə görünür güncel güncelleme işareti yok.'
          : lang === 'ar'
            ? 'لا توجد تحديثات حديثة ومرئية داخل البطاقة.'
          : 'Δεν υπάρχουν εμφανείς πρόσφατες ενημερώσεις στην καταχώριση.',
  };
  return evidenceById[issueId] || translateAuditText(lang, issue?.evidence);
};

const localizeIssueBlock = (
  lang: PageLang,
  issue: OfferPagePayload['audit']['issue_blocks'][number],
  state: NonNullable<OfferPagePayload['audit']>['current_state'],
) => {
  if (lang === 'ru') return issue;
  const issueId = String(issue?.id || '').trim();
  const translated = ISSUE_TRANSLATIONS[lang as keyof typeof ISSUE_TRANSLATIONS]?.[issueId];
  if (!translated) {
    return {
      ...issue,
      title: translateAuditText(lang, issue?.title),
      problem: translateAuditText(lang, issue?.problem),
      evidence: translateAuditText(lang, issue?.evidence),
      impact: translateAuditText(lang, issue?.impact),
      fix: translateAuditText(lang, issue?.fix),
    };
  }
  return {
    ...issue,
    title: translated.title,
    problem: translated.problem,
    evidence: buildLocalizedEvidence(lang, issueId, issue, state),
    impact: translated.impact,
    fix: translated.fix,
  };
};

const buildLocalizedSummary = (
  lang: PageLang,
  page: OfferPagePayload,
  text: typeof UI_TEXT.ru,
) => {
  const editorSummary = String(page.audit?.editor_blocks?.summary?.body || '').trim();
  const summaryText = editorSummary || String(page.audit?.summary_text || '').trim();
  if (lang === 'ru') return summaryText;
  const canonicalSummary = summaryText;
  if (canonicalSummary) {
    const translatedCanonicalSummary = translateAuditText(lang, canonicalSummary);
    if (translatedCanonicalSummary && translatedCanonicalSummary !== canonicalSummary) {
      return translatedCanonicalSummary;
    }
  }
  const state = page.audit?.current_state || {};
  const revenue = page.audit?.revenue_potential || {};
  const ratingText =
    state.rating !== null && state.rating !== undefined ? Number(state.rating).toFixed(1) : (lang === 'en' ? 'n/a' : 'n/a');
  const metricLocale = lang === 'el' ? 'el-GR' : lang === 'tr' ? 'tr-TR' : lang === 'ar' ? 'ar-EG' : 'en-GB';
  const reviewsCount = Number(state.reviews_count || 0).toLocaleString(metricLocale);
  const servicesCount = Number(state.services_count || 0).toLocaleString(metricLocale);
  const websiteState = state.has_website
    ? (lang === 'en' ? 'present' : lang === 'tr' ? 'var' : lang === 'ar' ? 'موجود' : 'υπάρχει')
    : (lang === 'en' ? 'missing' : lang === 'tr' ? 'yok' : lang === 'ar' ? 'غير موجود' : 'λείπει');
  const activityState = state.has_recent_activity
    ? (lang === 'en' ? 'present' : lang === 'tr' ? 'var' : lang === 'ar' ? 'موجود' : 'υπάρχει')
    : (lang === 'en' ? 'missing' : lang === 'tr' ? 'yok' : lang === 'ar' ? 'غير موجود' : 'λείπει');
  const healthLabel = localizedHealthLabel(lang, page.audit?.health_level, page.audit?.health_label);
  if (revenue.total_min || revenue.total_max) {
    const totalMin = formatMoney(lang, Number(revenue.total_min || 0));
    const totalMax = formatMoney(lang, Number(revenue.total_max || 0));
    const driver = String(revenue.dominant_driver || '').trim().toLowerCase();
    const driverLabel =
      driver === 'rating_gap'
        ? (lang === 'en' ? 'rating and trust' : lang === 'tr' ? 'puan ve güven' : lang === 'ar' ? 'التقييم والثقة' : 'βαθμολογία και εμπιστοσύνη')
        : driver === 'service_gap'
          ? (lang === 'en' ? 'service structure' : lang === 'tr' ? 'hizmet yapısı' : lang === 'ar' ? 'هيكلة الخدمات' : 'δομή υπηρεσιών')
          : (lang === 'en' ? 'card completeness' : lang === 'tr' ? 'profil bütünlüğü' : lang === 'ar' ? 'اكتمال البطاقة' : 'πληρότητα καταχώρισης');
    return lang === 'en'
      ? `${healthLabel}. Estimated monthly leakage caused by the listing: ${totalMin}–${totalMax}. The main loss driver right now is ${driverLabel}.`
      : lang === 'tr'
        ? `${healthLabel}. Profil nedeniyle tahmini aylık kayıp ${totalMin}–${totalMax}. Şu anda en büyük kayıp nedeni ${driverLabel}.`
        : lang === 'ar'
          ? `${healthLabel}. الخسارة الشهرية التقديرية بسبب البطاقة هي ${totalMin}–${totalMax}. العامل الرئيسي للخسارة الآن هو ${driverLabel}.`
          : `${healthLabel}. Η εκτιμώμενη μηνιαία απώλεια λόγω της καταχώρισης είναι ${totalMin}–${totalMax}. Ο βασικός παράγοντας απώλειας αυτή τη στιγμή είναι ${driverLabel}.`;
  }
  return lang === 'en'
    ? `${healthLabel}. Rating ${ratingText}, reviews ${reviewsCount}, services ${servicesCount}. Website: ${websiteState}, fresh activity: ${activityState}.`
    : lang === 'tr'
      ? `${healthLabel}. Puan ${ratingText}, yorum ${reviewsCount}, hizmet ${servicesCount}. Web sitesi: ${websiteState}, güncel aktivite: ${activityState}.`
      : lang === 'ar'
        ? `${healthLabel}. التقييم ${ratingText}، المراجعات ${reviewsCount}، الخدمات ${servicesCount}. الموقع الإلكتروني: ${websiteState}، النشاط الحديث: ${activityState}.`
        : `${healthLabel}. Βαθμολογία ${ratingText}, κριτικές ${reviewsCount}, υπηρεσίες ${servicesCount}. Ιστότοπος: ${websiteState}, πρόσφατη δραστηριότητα: ${activityState}.`;
};

const localizeActionPlanLines = (
  lang: PageLang,
  lines: string[],
) => {
  if (lang === 'ru') return lines;
  return lines.map((line) => translateAuditText(lang, line));
};

const normalizeMediaUrl = (raw?: string | null): string => {
  const value = String(raw || '').trim();
  if (!value) return '';
  let next = value;
  if (next.startsWith('//')) next = `https:${next}`;
  if (next.includes('{size}')) next = next.replaceAll('{size}', 'XXXL');
  if (next.includes('/%s')) next = next.replaceAll('/%s', '/XXXL');
  else if (next.includes('%s')) next = next.replaceAll('%s', 'XXXL');
  return next;
};

const pickFirstNonEmpty = (...values: Array<string | null | undefined>): string => {
  for (const value of values) {
    const text = String(value || '').trim();
    if (text) return text;
  }
  return '';
};

const extractStreet = (address?: string | null): string => {
  const text = String(address || '').trim();
  if (!text) return '';
  const parts = text.split(',').map((item) => item.trim()).filter(Boolean);
  if (parts.length === 0) return '';
  for (const part of parts) {
    const lower = part.toLowerCase();
    if (
      lower.includes('улиц') ||
      lower.includes('ул.') ||
      lower.includes('просп') ||
      lower.includes('наб') ||
      lower.includes('шоссе') ||
      lower.includes('бульвар') ||
      lower.includes('переул') ||
      lower.includes('коса') ||
      lower.includes('street') ||
      lower.includes('st') ||
      lower.includes('ave') ||
      lower.includes('sok') ||
      lower.includes('sokak') ||
      lower.includes('cad') ||
      lower.includes('caddesi') ||
      lower.includes('mah')
    ) {
      return part;
    }
  }
  const first = parts[0] || '';
  if (/\d/.test(first) && parts.length >= 2 && !/\d/.test(parts[1] || '')) {
    return `${first}, ${parts[1]}`;
  }
  return first;
};

const normalizeReviewPreview = (item: ReviewPreviewItem) => {
  const author = pickFirstNonEmpty(item.author, item.name, 'Клиент');
  const text = pickFirstNonEmpty(item.text, item.review);
  const orgReply = pickFirstNonEmpty(item.org_reply, item.reply_preview);
  const normalized = `${text} ${orgReply}`.toLowerCase();
  const isPlaceholder =
    normalized.includes('текст отзыва') ||
    normalized.includes('пример отзыва') ||
    normalized.includes('sample review') ||
    normalized.includes('demo review') ||
    normalized.includes('lorem ipsum');
  const hasMeaningfulContent = Boolean((text || orgReply) && !isPlaceholder);
  return { author, text, orgReply, rating: item.rating, hasMeaningfulContent };
};

const localizeReviewPreview = (lang: PageLang, item: ReturnType<typeof normalizeReviewPreview>) => ({
  ...item,
  author: lang === 'ru' ? item.author : translateAuditText(lang, item.author),
  text: translateAuditText(lang, item.text),
  orgReply: translateAuditText(lang, item.orgReply),
});

const normalizeNewsPreview = (item: NewsPreviewItem) => {
  const title = pickFirstNonEmpty(item.title);
  const text = pickFirstNonEmpty(item.text, item.body);
  const isDemoTemplate = title.toLowerCase().startsWith('пример новости:');
  const hasMeaningfulContent = Boolean((title || text) && !isDemoTemplate);
  return { title, text, hasMeaningfulContent };
};

const localizeNewsPreview = (lang: PageLang, item: ReturnType<typeof normalizeNewsPreview>) => ({
  ...item,
  title: translateAuditText(lang, item.title),
  text: translateAuditText(lang, item.text),
});

const SERVICE_PLACEHOLDER_NAMES = new Set([
  'Общая услуга без структуры',
  'Услуга без цены',
  'Нет отдельных направлений',
]);

const isPlaceholderService = (
  item: NonNullable<OfferPagePayload['audit']>['services_preview'][number],
) => {
  const currentName = pickFirstNonEmpty(item.current_name, item.improved_name);
  const description = pickFirstNonEmpty(item.description);
  if (SERVICE_PLACEHOLDER_NAMES.has(currentName)) return true;
  const normalized = `${currentName} ${description}`.toLowerCase();
  return (
    normalized.includes('общая услуга без структуры') ||
    normalized.includes('услуга без цены') ||
    normalized.includes('нет отдельных направлений')
  );
};

const localizeServicePreview = (
  lang: PageLang,
  item: NonNullable<OfferPagePayload['audit']>['services_preview'][number],
) => ({
  ...item,
  current_name: translateAuditText(lang, item.current_name),
  improved_name: translateAuditText(lang, item.improved_name),
  description: translateAuditText(lang, item.description),
  category: translateAuditText(lang, item.category),
  source: translateAuditText(lang, item.source),
});

const RUB_TO_USD = 100;

const formatMoney = (lang: PageLang, value?: number | null): string => {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  if (lang === 'ru') return `${Number(value).toLocaleString('ru-RU')} ₽`;
  const usdValue = Math.max(1, Math.round(Number(value) / RUB_TO_USD));
  return `$${usdValue.toLocaleString(lang === 'el' ? 'el-GR' : lang === 'tr' ? 'tr-TR' : lang === 'ar' ? 'ar-EG' : 'en-GB')}`;
};

const stateBadgeClass = (score?: number) => {
  const safe = Number(score || 0);
  if (safe >= 80) return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (safe >= 55) return 'bg-amber-50 text-amber-700 border-amber-200';
  return 'bg-rose-50 text-rose-700 border-rose-200';
};

const PublicPartnershipOfferPage: React.FC = () => {
  const { offerSlug } = useParams<{ offerSlug: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<OfferPagePayload | null>(null);

  useEffect(() => {
    const run = async () => {
      if (!offerSlug) return;
      try {
        setLoading(true);
        setError(null);
        try {
          const data = await newAuth.makeRequest(`/partnership/public/offer/${encodeURIComponent(offerSlug)}`, {
            method: 'GET',
          });
          const nextPage: OfferPagePayload | null = data?.page || null;
          setPage(nextPage);
        } catch (_) {
          const fallback = await newAuth.makeRequest(`/public/report-offer/${encodeURIComponent(offerSlug)}`, {
            method: 'GET',
          });
          const nextPage: OfferPagePayload | null = fallback?.page || null;
          setPage(nextPage);
        }
      } catch (e: any) {
        setError(e.message || 'Не удалось загрузить страницу');
        setPage(null);
      } finally {
        setLoading(false);
      }
    };
    void run();
  }, [offerSlug]);

  const requestedLang = String(searchParams.get('lang') || '').trim().toLowerCase();
  const enabledLanguages = (() => {
    const explicitlyEnabled = normalizePageLanguages(page?.enabled_languages);
    if (explicitlyEnabled.length > 0) {
      return explicitlyEnabled;
    }
    const availableLanguages = normalizePageLanguages(page?.available_languages);
    if (availableLanguages.length > 0) {
      return availableLanguages;
    }
    return supportedPublicAuditLanguages;
  })();
  const availableLanguages = (() => {
    const merged: PageLang[] = [];
    const pushUnique = (items: PageLang[]) => {
      items.forEach((item) => {
        if (!merged.includes(item)) {
          merged.push(item);
        }
      });
    };
    const availableFromPage = normalizePageLanguages(page?.available_languages);
    const enabledFromPage = normalizePageLanguages(page?.enabled_languages);
    if (availableFromPage.length > 0 || enabledFromPage.length > 0) {
      pushUnique(availableFromPage);
      pushUnique(enabledFromPage);
      return merged;
    }
    pushUnique(supportedPublicAuditLanguages);
    return merged.length > 0 ? merged : supportedPublicAuditLanguages;
  })();
  const switchableLanguages = availableLanguages;
  const preferredLang = String(page?.primary_language || page?.preferred_language || '').trim().toLowerCase();
  const autoLang: PageLang = (() => {
    const context = `${page?.city || ''} ${page?.address || ''}`.toLowerCase();
    if (isPageLang(requestedLang) && switchableLanguages.includes(requestedLang)) return requestedLang;
    if (isPageLang(preferredLang) && enabledLanguages.includes(preferredLang)) return preferredLang;
    if ((context.includes('cyprus') || context.includes('κύπρ') || context.includes('paphos') || context.includes('πάφος')) && switchableLanguages.includes('en')) return 'en';
    if ((context.includes('turkey') || context.includes('türkiye') || context.includes('istanbul') || context.includes('fethiye') || context.includes('ölüdeniz')) && switchableLanguages.includes('tr')) return 'tr';
    if (enabledLanguages.includes('ru')) return 'ru';
    return switchableLanguages[0] || enabledLanguages[0] || 'en';
  })();
  const lang: PageLang = autoLang;

  const startCheckoutFromAudit = async (tierId: 'starter' | 'professional' | 'concierge') => {
    const token = newAuth.getToken();
    let provider = 'yookassa';
    try {
      const providerResp = await fetch('/api/geo/payment-provider');
      const providerData = await providerResp.json();
      provider = String(providerData?.payment_provider || '').trim().toLowerCase() === 'stripe' ? 'stripe' : 'yookassa';
    } catch {
      provider = 'yookassa';
    }

    let email = '';
    if (!token) {
      email = window.prompt('Введите email, на который оформить доступ к LocalOS')?.trim() || '';
      if (!email) {
        return;
      }
    }

    try {
      const response = await fetch('/api/billing/checkout/session/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          provider,
          entry_point: 'public_audit',
          channel: 'web',
          tariff_id: tierId,
          email: email || undefined,
          maps_url: String(page?.source_url || '').trim() || undefined,
          normalized_maps_url: String(page?.source_url || '').trim() || undefined,
          audit_slug: String(offerSlug || '').trim() || undefined,
          audit_public_url: window.location.href,
          source: 'public_audit_page',
          payload_json: {
            business_name: String(page?.display_name || page?.name || '').trim(),
            city: String(page?.city || '').trim(),
            address: String(page?.address || '').trim(),
          },
        }),
      });
      const data = await response.json();
      const redirectUrl = String(data?.confirmation_url || data?.url || '').trim();
      if (!response.ok || !redirectUrl) {
        throw new Error(String(data?.error || 'Не удалось создать сессию оплаты'));
      }
      window.location.href = redirectUrl;
    } catch (checkoutError) {
      alert(checkoutError instanceof Error ? checkoutError.message : 'Не удалось перейти к оплате');
    }
  };
  const locale = lang === 'el' ? 'el-GR' : lang === 'tr' ? 'tr-TR' : lang === 'ar' ? 'ar-EG' : lang === 'ru' ? 'ru-RU' : 'en-GB';
  const text = UI_TEXT[lang] || UI_TEXT.en;
  const interpolate = (template: string, values: Record<string, string | number>) => {
    let out = template;
    Object.entries(values).forEach(([key, value]) => {
      out = out.replaceAll(`{${key}}`, String(value));
    });
    return out;
  };
  const formatValue = (value?: number | null): string => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
    return Number(value).toLocaleString(locale);
  };
  const languageLabels: Record<PageLang, string> = {
    en: 'EN',
    ru: 'RU',
    es: 'ES',
    de: 'DE',
    fr: 'FR',
    el: 'EL',
    th: 'TH',
    tr: 'TR',
    ar: 'AR',
    ha: 'HA',
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="rounded-xl border bg-white p-6 text-sm text-muted-foreground">{text.loading}</div>
      </div>
    );
  }

  if (error || !page) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-8">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
          {error || text.notFound}
        </div>
      </div>
    );
  }

  const rawFindings = Array.isArray(page.audit?.findings) ? page.audit?.findings || [] : [];
  const rawActions = Array.isArray(page.audit?.recommended_actions) ? page.audit?.recommended_actions || [] : [];
  const rawIssueBlocks = Array.isArray(page.audit?.issue_blocks) ? page.audit?.issue_blocks || [] : [];
  const editorBlocks = page.audit?.editor_blocks || {};
  const issueBlocks = rawIssueBlocks.map((item) => localizeIssueBlock(lang, item, page.audit?.current_state || {}));
  const editorTopIssues = Array.isArray(editorBlocks.top_issues?.items) ? editorBlocks.top_issues?.items || [] : [];
  const topIssues = editorTopIssues.length > 0
    ? editorTopIssues.map((item, index) => ({
        id: `editor-top-${index}`,
        title: translateAuditText(lang, item?.title),
        priority: translateAuditText(lang, item?.priority),
        problem: translateAuditText(lang, item?.body),
      }))
    : issueBlocks.slice(0, 3).map((item) => ({
        id: item.id,
        title: item.title,
        priority: item.priority,
        problem: item.problem,
      }));
  const findings = rawFindings.length > 0
    ? rawFindings.map((item, index) => ({
        ...item,
        title: issueBlocks[index]?.title || translateAuditText(lang, item.title),
        description: issueBlocks[index]?.problem || translateAuditText(lang, item.description),
      }))
    : issueBlocks.map((item) => ({
        code: String(item.id || ''),
        severity: String(item.priority || 'medium'),
        title: String(item.title || ''),
        description: String(item.problem || ''),
      }));
  const actions = rawActions.length > 0
    ? rawActions.map((item, index) => ({
        ...item,
        title: issueBlocks[index]?.title || translateAuditText(lang, item.title),
        description: issueBlocks[index]?.fix || translateAuditText(lang, item.description),
      }))
    : issueBlocks.map((item) => ({
        priority: String(item.priority || 'medium'),
        title: String(item.title || ''),
        description: String(item.fix || ''),
      }));
  const actionPlan = editorBlocks.action_plan?.sections && Array.isArray(editorBlocks.action_plan.sections)
    ? editorBlocks.action_plan.sections.reduce<{ next_24h: string[]; next_7d: string[]; ongoing: string[] }>((acc, section) => {
        const key = String(section?.key || '').trim();
        if (key === 'next_24h' || key === 'next_7d' || key === 'ongoing') {
          acc[key] = Array.isArray(section?.items) ? section.items : [];
        }
        return acc;
      }, { next_24h: [], next_7d: [], ongoing: [] })
    : page.audit?.action_plan || {};
  const servicesRaw = Array.isArray(page.audit?.services_preview) ? page.audit?.services_preview || [] : [];
  const services = servicesRaw
    .filter((item) => !isPlaceholderService(item))
    .map((item) => localizeServicePreview(lang, item));
  const reviewsRaw = Array.isArray(page.audit?.reviews_preview) ? page.audit?.reviews_preview || [] : [];
  const newsRaw = Array.isArray(page.audit?.news_preview) ? page.audit?.news_preview || [] : [];
  const reviews = reviewsRaw
    .map((item) => normalizeReviewPreview(item))
    .filter((item) => item.hasMeaningfulContent)
    .map((item) => localizeReviewPreview(lang, item));
  const news = newsRaw
    .map((item) => normalizeNewsPreview(item))
    .filter((item) => item.hasMeaningfulContent)
    .map((item) => localizeNewsPreview(lang, item));
  const photos = (Array.isArray(page.photo_urls) ? page.photo_urls || [] : [])
    .map((item) => normalizeMediaUrl(item))
    .filter(Boolean);
  const logoUrl = normalizeMediaUrl(page.logo_url || '');
  const state = page.audit?.current_state || {};
  const parse = page.audit?.parse_context || {};
  const isNetworkAudit = String(page.audit?.audit_profile || '').trim().toLowerCase().startsWith('network_')
    || String(parse.scope || '').trim().toLowerCase() === 'network';
  const confirmedServicesCount = Number(state.services_count || 0);
  const hasServicesPreviewOnly = confirmedServicesCount <= 0 && services.length > 0;
  const locationsCount = Number(state.locations_count || 0);
  const unverifiedLocationsCount = Number(state.unverified_locations_count || 0);
  const servicesMetricValue = confirmedServicesCount > 0 ? formatValue(confirmedServicesCount) : '—';
  const servicesMetricLabel = isNetworkAudit
    ? (lang === 'ru' ? 'Точки с меню/товарами' : text.services)
    : text.services;
  const servicesMetricHint =
    isNetworkAudit && lang === 'ru'
      ? `${formatValue(confirmedServicesCount)} из ${formatValue(locationsCount)} точек: в карточках найдено меню или товары.`
      : lang === 'en'
      ? hasServicesPreviewOnly
        ? 'Only service examples are available here; the total count is not confirmed.'
        : 'The count is based on the parsed service list.'
      : lang === 'tr'
        ? hasServicesPreviewOnly
          ? 'Burada yalnızca hizmet örnekleri var; toplam sayı doğrulanmadı.'
          : 'Sayı, ayrıştırılan hizmet listesinden alınır.'
        : lang === 'ar'
          ? hasServicesPreviewOnly
            ? 'المعروض هنا أمثلة للخدمات فقط، أما العدد الإجمالي فلم يتم تأكيده.'
            : 'العدد مبني على قائمة الخدمات التي تم استخراجها.'
          : lang === 'el'
            ? hasServicesPreviewOnly
              ? 'Εδώ εμφανίζονται μόνο παραδείγματα υπηρεσιών και όχι επιβεβαιωμένος συνολικός αριθμός.'
              : 'Ο αριθμός βασίζεται στη λίστα υπηρεσιών που αναγνωρίστηκε.'
            : hasServicesPreviewOnly
              ? 'Здесь показаны только примеры услуг, а не подтверждённое общее число.'
              : 'Число основано на распознанном списке услуг.';
  const cadence = page.audit?.cadence || {};
  const cadenceNews = Number(cadence.news_posts_per_month_min || 4);
  const cadencePhotos = Number(cadence.photos_per_month_min || 8);
  const cadenceReplyHours = Number(cadence.reviews_response_hours_max || 48);
  const revenue = page.audit?.revenue_potential || {};
  const score = Number(page.audit?.summary_score || 0);
  const resolvedCity = String(page.city || '').trim() || String(page.address || '').split(',', 1)[0]?.trim() || '';
  const resolvedStreet = extractStreet(page.address);
  const displayName = pickFirstNonEmpty(
    page.display_name,
    [page.name, resolvedCity, resolvedStreet].filter(Boolean).join(', '),
    page.name,
    lang === 'en' ? 'Company' : lang === 'el' ? 'Εταιρεία' : lang === 'tr' ? 'İşletme' : lang === 'ar' ? 'الشركة' : 'Компания',
  );
  const mapsAnalysis = Array.isArray(page.maps_analysis) ? page.maps_analysis || [] : [];
  const multipleMaps = mapsAnalysis.length >= 2;
  const bestMapByReviews = mapsAnalysis.reduce<OfferPagePayload['maps_analysis'][number] | null>((best, item) => {
    if (!item) return best;
    if (!best) return item;
    return Number(item.reviews_total || 0) > Number(best.reviews_total || 0) ? item : best;
  }, null);
  const bestMapByRating = mapsAnalysis.reduce<OfferPagePayload['maps_analysis'][number] | null>((best, item) => {
    if (!item) return best;
    if (!best) return item;
    const currentRating = Number(item.rating || 0);
    const bestRating = Number(best.rating || 0);
    if (currentRating === bestRating) {
      return Number(item.reviews_total || 0) > Number(best.reviews_total || 0) ? item : best;
    }
    return currentRating > bestRating ? item : best;
  }, null);
  const priorityRecommendation = (() => {
    const yandex = mapsAnalysis.find((item) => item?.source === 'yandex_maps');
    const google = mapsAnalysis.find((item) => item?.source === 'google_maps');
    if (yandex && google) {
      const yandexReviews = Number(yandex.reviews_total || 0);
      const googleReviews = Number(google.reviews_total || 0);
      const reviewsGap = googleReviews - yandexReviews;
      if (reviewsGap >= 15) {
        return interpolate(text.priorityYandexReviews, { gap: reviewsGap });
      }
      const yandexRating = Number(yandex.rating || 0);
      const googleRating = Number(google.rating || 0);
      if (googleRating - yandexRating >= 0.2) {
        return text.priorityYandexRating;
      }
      if (yandexReviews - googleReviews >= 15) {
        return text.priorityGoogleReviews;
      }
    }
    return text.priorityGeneric;
  })();
  const localizedHealth = localizedHealthLabel(lang, page.audit?.health_level, page.audit?.health_label);
  const localizedSummary = buildLocalizedSummary(lang, page, text);
  const localizedActionPlan = {
    next_24h: localizeActionPlanLines(lang, Array.isArray(actionPlan.next_24h) ? actionPlan.next_24h : []),
    next_7d: localizeActionPlanLines(lang, Array.isArray(actionPlan.next_7d) ? actionPlan.next_7d : []),
    ongoing: localizeActionPlanLines(lang, Array.isArray(actionPlan.ongoing) ? actionPlan.ongoing : []),
  };
  const reasoningLabels =
    lang === 'en'
      ? {
          profile: 'Audit profile',
          strongDemand: 'The card responds best to searches for',
          weakDemand: 'The card responds weaker to searches for',
          why: 'Why',
          photos: 'Photo shots to add',
        }
      : lang === 'el'
        ? {
            profile: 'Προφίλ ελέγχου',
            strongDemand: 'Η καταχώριση ανταποκρίνεται καλύτερα σε αναζητήσεις για',
            weakDemand: 'Η καταχώριση ανταποκρίνεται πιο αδύναμα σε αναζητήσεις για',
            why: 'Γιατί',
            photos: 'Φωτογραφίες που λείπουν',
          }
        : lang === 'tr'
          ? {
              profile: 'Denetim profili',
              strongDemand: 'Kart en iyi şu arama taleplerine cevap veriyor',
              weakDemand: 'Kart şu arama taleplerine daha zayıf cevap veriyor',
              why: 'Neden',
              photos: 'Eklenmesi gereken fotoğraflar',
            }
        : lang === 'ar'
          ? {
              profile: 'ملف التدقيق',
              strongDemand: 'البطاقة تستجيب بشكل أفضل لطلبات البحث عن',
              weakDemand: 'البطاقة تستجيب بشكل أضعف لطلبات البحث عن',
              why: 'لماذا',
              photos: 'الصور التي يجب إضافتها',
            }
        : {
            profile: 'Профиль аудита',
            strongDemand: 'Карточка лучше всего отвечает на запросы',
            weakDemand: 'Карточка слабее отвечает на запросы',
            why: 'Почему',
            photos: 'Каких фото не хватает',
          };
  const editorStrongDemandRaw = Array.isArray(editorBlocks.strong_demand?.items) ? editorBlocks.strong_demand?.items || [] : [];
  const editorWeakDemandRaw = Array.isArray(editorBlocks.weak_demand?.items) ? editorBlocks.weak_demand?.items || [] : [];
  const editorWhyRaw = Array.isArray(editorBlocks.why?.items) ? editorBlocks.why?.items || [] : [];
  const bestFitProfileRaw = Array.isArray(page.audit?.best_fit_customer_profile) && page.audit?.best_fit_customer_profile.length > 0
    ? page.audit?.best_fit_customer_profile || []
    : Array.isArray(page.audit?.best_fit_guest_profile)
      ? page.audit?.best_fit_guest_profile || []
      : [];
  const weakFitProfileRaw = Array.isArray(page.audit?.weak_fit_customer_profile) && page.audit?.weak_fit_customer_profile.length > 0
    ? page.audit?.weak_fit_customer_profile || []
    : Array.isArray(page.audit?.weak_fit_guest_profile)
      ? page.audit?.weak_fit_guest_profile || []
      : [];
  const searchIntentsRaw = Array.isArray(page.audit?.search_intents_to_target) ? page.audit?.search_intents_to_target || [] : [];
  const photoShotsRaw = Array.isArray(page.audit?.photo_shots_missing) ? page.audit?.photo_shots_missing || [] : [];
  const bestFitProfile = bestFitProfileRaw.map((item) => translateAuditText(lang, item));
  const weakFitProfile = weakFitProfileRaw.map((item) => translateAuditText(lang, item));
  const searchIntents = searchIntentsRaw.map((item) => translateAuditText(lang, item));
  const photoShots = photoShotsRaw.map((item) => translateAuditText(lang, item));
  const positioningWhyRaw = rawIssueBlocks
    .filter((item) => String(item.section || '').trim().toLowerCase() === 'positioning')
    .flatMap((item) => [item.problem, item.evidence])
    .filter((item): item is string => Boolean(String(item || '').trim()));
  const servicesCountForWhy = Number(state.services_count || 0);
  const pricedServicesCountForWhy = Number(state.services_with_price_count || 0);
  const auditProfileForWhy = String(page.audit?.audit_profile || '').trim().toLowerCase();
  const fallbackPositioningWhy = [
    servicesCountForWhy > 0
      ? pricedServicesCountForWhy > 0
        ? `В карточке найдено ${formatValue(servicesCountForWhy)} услуг с ценами, но пациенту всё равно нужно быстро понять, к какому врачу или направлению идти.`
        : `В карточке найдено ${formatValue(servicesCountForWhy)} услуг, но без ценовых ориентиров сложнее сравнить варианты и решиться на запись.`
      : '',
    auditProfileForWhy === 'medical'
      ? 'Для медицинской карточки важны не только услуги, но и понятные сценарии выбора: первичный приём, повторный приём, конкретный специалист, диагностика.'
      : '',
    !state.has_recent_activity
      ? 'Свежей активности в карточке не видно: новости и обновления не поддерживают ключевые направления поиска.'
      : '',
  ].filter((item) => item.trim());
  const isCapriAudit = String(offerSlug || '').trim().toLowerCase() === 'dom-krasoty-capri-oblastnaya-ulitsa';
  const capriStrongDemand = ['педикюр', 'косметология', 'оформление бровей'];
  const capriWeakDemand = ['салон красоты рядом', 'выбор между направлениями услуг', 'поиск услуги по цене'];
  const capriWhy = [
    'в карточке уже видны отдельные направления, но не объяснено, какие из них ключевые',
    'часть услуг выглядит как общий список, а не как понятные сценарии выбора',
    'не везде хватает цены и короткого объяснения, чем одна услуга отличается от другой',
  ];
  const positioningWhy = isCapriAudit && lang === 'ru'
    ? capriWhy
    : editorWhyRaw.length > 0
      ? Array.from(new Set(editorWhyRaw.map((item) => translateAuditText(lang, item).trim()))).slice(0, 5)
    : positioningWhyRaw.length > 0
      ? Array.from(new Set(positioningWhyRaw.map((item) => translateAuditText(lang, item).trim()))).slice(0, 3)
      : fallbackPositioningWhy.slice(0, 3);
  const strongDemand = isCapriAudit && lang === 'ru'
    ? capriStrongDemand
    : editorStrongDemandRaw.length > 0
      ? editorStrongDemandRaw.map((item) => translateAuditText(lang, item)).slice(0, 5)
    : (searchIntents.length > 0 ? searchIntents : bestFitProfile).slice(0, 5);
  const weakDemand = isCapriAudit && lang === 'ru'
    ? capriWeakDemand
    : editorWeakDemandRaw.length > 0
      ? editorWeakDemandRaw.map((item) => translateAuditText(lang, item)).slice(0, 5)
    : weakFitProfile.slice(0, 4);
  const auditProfileLabel = translateAuditText(
    lang,
    String(page.audit?.audit_profile_label || page.audit?.audit_profile || '').trim(),
  );

  const quickState = [
    {
      label: isNetworkAudit && lang === 'ru' ? 'Меню/товары в точках' : text.stateServices,
      ok: Number(state.services_count || 0) > 0,
      hint: isNetworkAudit && lang === 'ru'
        ? `${formatValue(state.services_count)} из ${formatValue(locationsCount)} точек`
        : Number(state.services_count || 0) > 0 ? `${formatValue(state.services_count)} ${text.found}` : text.servicesMissing,
    },
    {
      label: text.stateWebsite,
      ok: Boolean(state.has_website),
      hint: state.has_website ? text.websitePresent : text.websiteMissing,
    },
    {
      label: text.stateReviews,
      ok: Number(state.unanswered_reviews_count || 0) <= 3,
      hint:
        Number(state.unanswered_reviews_count || 0) > 0
          ? `${text.noAnswerPrefix}: ${formatValue(state.unanswered_reviews_count)}`
          : text.repliesExist,
    },
    {
      label: text.stateActivity,
      ok: Boolean(state.has_recent_activity),
      hint: isNetworkAudit && lang === 'ru' && unverifiedLocationsCount > 0
        ? `С неактуальными или устаревшими данными: ${formatValue(unverifiedLocationsCount)} точек`
        : state.has_recent_activity ? text.activityPresent : text.activityMissing,
    },
  ];

  return (
    <div dir={lang === 'ar' ? 'rtl' : 'ltr'} className="min-h-screen bg-[radial-gradient(ellipse_at_top_right,_rgba(56,189,248,0.18),_transparent_45%),radial-gradient(ellipse_at_bottom_left,_rgba(14,165,233,0.16),_transparent_40%),linear-gradient(to_bottom,_#f8fafc,_#ffffff)]">
      <div className="mx-auto max-w-6xl px-4 py-8 space-y-5">
        <section className="rounded-2xl border border-sky-100 bg-white/90 backdrop-blur-sm p-6 md:p-8 shadow-sm">
          <div className="flex flex-col md:flex-row gap-4 md:items-start md:justify-between">
            <div className="flex items-center gap-4">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt={text.companyLogo}
                className="h-16 w-16 md:h-20 md:w-20 rounded-xl border border-sky-100 object-cover bg-white"
              />
            ) : null}
              <div>
                <h1 className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">{displayName}</h1>
                <p className="mt-1 text-sm text-slate-600 flex flex-wrap gap-2 items-center">
                  {resolvedCity ? (
                    <>
                      <span className="inline-flex items-center gap-1">
                        <MapPin className="w-4 h-4" />
                        {resolvedCity}
                      </span>
                      <span>•</span>
                    </>
                  ) : null}
                  <span>{page.category || text.categoryMissing}</span>
                </p>
                {page.address ? <p className="text-sm text-slate-500 mt-1">{page.address}</p> : null}
                {parse.last_parse_at ? (
                  <p className="text-xs text-slate-500 mt-2">
                    {text.lastAudit}: {new Date(parse.last_parse_at).toLocaleString(locale)}
                  </p>
                ) : null}
                {page.processing ? (
                  <p className="mt-2 text-sm text-amber-700">
                    {lang === 'ru' ? (page.processing_message || text.processingFallback) : text.processingFallback}
                  </p>
                ) : null}
              </div>
            </div>
            <div className="md:text-right">
              {switchableLanguages.length > 1 ? (
                <div className="mb-3 flex flex-wrap justify-start gap-2 md:justify-end">
                  {switchableLanguages.map((code) => {
                    const nextParams = new URLSearchParams(searchParams);
                    nextParams.set('lang', code);
                    const href = `${window.location.pathname}?${nextParams.toString()}`;
                    const active = code === lang;
                    return (
                      <a
                        key={code}
                        href={href}
                        className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                          active
                            ? 'border-sky-500 bg-sky-50 text-sky-700'
                            : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'
                        }`}
                      >
                        {languageLabels[code]}
                      </a>
                    );
                  })}
                </div>
              ) : null}
              <div className="text-xs uppercase tracking-wider text-slate-500">{text.cardScore}</div>
              <div className="text-3xl font-bold text-slate-900 mt-1">{score}/100</div>
              <div className={`inline-flex mt-2 px-3 py-1 rounded-full border text-xs font-semibold ${stateBadgeClass(score)}`}>
                {page.processing && lang !== 'ru' ? text.stateUnknown : (localizedHealth || text.stateUnknown)}
              </div>
            </div>
          </div>
          <div className="mt-6 grid grid-cols-1 md:grid-cols-4 gap-3">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">{text.rating}</div>
              <div className="mt-1 text-xl font-semibold text-slate-900 flex items-center gap-2">
                <Star className="w-4 h-4 text-amber-500" />
                {state.rating ? Number(state.rating).toFixed(1) : '—'}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">{text.reviews}</div>
              <div className="mt-1 text-xl font-semibold text-slate-900">{formatValue(state.reviews_count)}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">{servicesMetricLabel}</div>
              <div className="mt-1 text-xl font-semibold text-slate-900">{servicesMetricValue}</div>
              <div className="mt-2 text-xs text-slate-500">{servicesMetricHint}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">{text.monthlyPotential}</div>
              <div className="mt-1 text-sm font-semibold text-slate-900">
                {revenue.total_min || revenue.total_max
                  ? `${formatMoney(lang, revenue.total_min)} — ${formatMoney(lang, revenue.total_max)}`
                  : text.estimateUnavailable}
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-sky-600" />
            {text.currentStateTitle}
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            {text.currentStateText}
          </p>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-3">
            {quickState.map((row) => (
              <div key={row.label} className="rounded-xl border border-slate-200 p-4 bg-slate-50/70">
                <div className="flex items-center gap-2">
                  {row.ok ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-rose-600" />
                  )}
                  <span className="font-medium text-slate-900">{row.label}</span>
                </div>
                <p className="mt-1 text-sm text-slate-600">{row.hint}</p>
              </div>
            ))}
          </div>
        </section>

        {(strongDemand.length > 0 || weakDemand.length > 0 || positioningWhy.length > 0 || photoShots.length > 0) ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-violet-600" />
                {lang === 'en' ? 'Positioning and search scenarios' : lang === 'el' ? 'Τοποθέτηση και σενάρια αναζήτησης' : lang === 'tr' ? 'Konumlandırma ve arama senaryoları' : lang === 'ar' ? 'التموضع وسيناريوهات البحث' : 'Позиционирование и сценарии поиска'}
              </h2>
              {auditProfileLabel ? (
                <div className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
                  {reasoningLabels.profile}: {auditProfileLabel}
                </div>
              ) : null}
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
              {strongDemand.length > 0 ? (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                  <div className="text-sm font-semibold text-slate-900">{reasoningLabels.strongDemand}</div>
                  <div className="mt-2 space-y-2 text-sm text-slate-700">
                    {strongDemand.map((item, idx) => <div key={`best-${idx}`}>• {item}</div>)}
                  </div>
                </div>
              ) : null}
              {weakDemand.length > 0 ? (
                <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-4">
                  <div className="text-sm font-semibold text-slate-900">{reasoningLabels.weakDemand}</div>
                  <div className="mt-2 space-y-2 text-sm text-slate-700">
                    {weakDemand.map((item, idx) => <div key={`weak-${idx}`}>• {item}</div>)}
                  </div>
                </div>
              ) : null}
              {positioningWhy.length > 0 ? (
                <div className="rounded-xl border border-sky-200 bg-sky-50/60 p-4">
                  <div className="text-sm font-semibold text-slate-900">{reasoningLabels.why}</div>
                  <div className="mt-2 space-y-2 text-sm text-slate-700">
                    {positioningWhy.map((item, idx) => <div key={`why-${idx}`}>• {item}</div>)}
                  </div>
                </div>
              ) : null}
            </div>
            {photoShots.length > 0 ? (
              <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                  <div className="text-sm font-semibold text-slate-900">{reasoningLabels.photos}</div>
                  <div className="mt-2 space-y-2 text-sm text-slate-700">
                    {photoShots.map((item, idx) => <div key={`photo-${idx}`}>• {item}</div>)}
                  </div>
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {multipleMaps ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">{text.allMapsTitle}</h2>
            <p className="text-sm text-slate-600 mt-1">
              {text.allMapsText}
            </p>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50/70 p-4">
                <div className="text-xs uppercase tracking-wide text-emerald-700">{text.bestReviews}</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{bestMapByReviews?.label || '—'}</div>
                <div className="mt-1 text-sm text-slate-700">{formatValue(bestMapByReviews?.reviews_total)} {text.reviews.toLowerCase()}</div>
              </div>
              <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
                <div className="text-xs uppercase tracking-wide text-amber-700">{text.bestRating}</div>
                <div className="mt-1 text-sm font-semibold text-slate-900">{bestMapByRating?.label || '—'}</div>
                <div className="mt-1 text-sm text-slate-700">
                  {bestMapByRating?.rating !== null && bestMapByRating?.rating !== undefined ? Number(bestMapByRating.rating).toFixed(1) : '—'}
                </div>
              </div>
              <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-4">
                <div className="text-xs uppercase tracking-wide text-sky-700">{text.priority}</div>
                <div className="mt-1 text-sm text-slate-800">{priorityRecommendation}</div>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {mapsAnalysis.map((item, idx) => (
                <div key={`${item.source || item.label || 'map'}-${idx}`} className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-slate-900">{item.label || item.source || text.sourceFallback}</div>
                    {item.url ? (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-sky-700 hover:text-sky-800 inline-flex items-center gap-1"
                      >
                        {text.open}
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : null}
                  </div>
                  <div className="mt-3 space-y-1 text-sm text-slate-700">
                    <div>{text.rating}: <span className="font-semibold text-slate-900">{item.rating !== null && item.rating !== undefined ? Number(item.rating).toFixed(1) : '—'}</span></div>
                    <div>{text.reviews}: <span className="font-semibold text-slate-900">{formatValue(item.reviews_total)}</span></div>
                    {item.last_sync_at ? (
                      <div className="text-xs text-slate-500">
                        {text.updated}: {new Date(item.last_sync_at).toLocaleDateString(locale)}
                      </div>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-violet-600" />
            {text.improveFirstTitle}
          </h2>
          {localizedSummary ? <p className="text-sm text-slate-600 mt-1">{localizedSummary}</p> : null}
          {topIssues.length > 0 && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
              {topIssues.slice(0, 3).map((item, idx) => (
                <div key={`${item.id || item.title || 'top'}-${idx}`} className="rounded-xl border border-amber-200 bg-amber-50/60 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-900">{item.title || text.issueFallback}</div>
                    {item.priority ? (
                      <div className="text-xs font-semibold text-amber-700 uppercase">{item.priority}</div>
                    ) : null}
                  </div>
                  {item.problem ? <div className="mt-1 text-xs text-slate-700">{item.problem}</div> : null}
                </div>
              ))}
            </div>
          )}
          <div className="mt-4 space-y-3">
            {issueBlocks.length > 0 ? (
              issueBlocks.slice(0, 6).map((item, idx) => (
                <div key={`${item.id || item.title || 'item'}-${idx}`} className="rounded-xl border border-violet-100 bg-violet-50/50 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-semibold text-slate-900">{idx + 1}. {item.title || text.issueFallback}</div>
                    {item.priority ? <div className="text-xs font-semibold text-violet-700 uppercase">{item.priority}</div> : null}
                  </div>
                  <div className="text-sm text-slate-700 mt-1">
                    <span className="font-medium">{text.problem}:</span> {item.problem || text.noDescription}
                  </div>
                  {item.evidence ? (
                    <div className="text-sm text-slate-700 mt-1">
                      <span className="font-medium">{text.fact}:</span> {item.evidence}
                    </div>
                  ) : null}
                  {item.impact ? (
                    <div className="text-sm text-slate-700 mt-1">
                      <span className="font-medium">{text.impact}:</span> {item.impact}
                    </div>
                  ) : null}
                  {item.fix ? (
                    <div className="text-sm text-slate-700 mt-1">
                      <span className="font-medium">{text.whatToDo}:</span> {item.fix}
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              (findings.length > 0 ? findings : actions).slice(0, 6).map((item, idx) => (
                <div key={`${item.title || 'item'}-${idx}`} className="rounded-xl border border-violet-100 bg-violet-50/50 p-4">
                  <div className="text-sm font-semibold text-slate-900">{idx + 1}. {item.title || text.recommendationFallback}</div>
                  <div className="text-sm text-slate-700 mt-1">{item.description || text.noDescription}</div>
                </div>
              ))
            )}
          </div>
          <div className="mt-4 rounded-xl border border-sky-100 bg-sky-50/60 p-4">
            <div className="text-sm font-semibold text-slate-900">{text.cadenceTitle}</div>
            <div className="mt-2 text-sm text-slate-700">
              {interpolate(text.cadenceText, { news: cadenceNews, photos: cadencePhotos, hours: cadenceReplyHours })}
            </div>
          </div>
          {((actionPlan.next_24h || []).length > 0 || (actionPlan.next_7d || []).length > 0 || (actionPlan.ongoing || []).length > 0) ? (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
              <div className="text-sm font-semibold text-slate-900">{text.implementationPlan}</div>
              <div className="mt-2 text-sm text-slate-700 space-y-2">
                <div>
                  <div className="font-medium text-slate-900">{text.in24h}</div>
                  {localizedActionPlan.next_24h.slice(0, 3).map((line, idx) => (
                    <div key={`p24-${idx}`}>• {line}</div>
                  ))}
                </div>
                <div>
                  <div className="font-medium text-slate-900">{text.in7d}</div>
                  {localizedActionPlan.next_7d.slice(0, 3).map((line, idx) => (
                    <div key={`p7-${idx}`}>• {line}</div>
                  ))}
                </div>
                <div>
                  <div className="font-medium text-slate-900">{text.ongoing}</div>
                  {localizedActionPlan.ongoing.slice(0, 3).map((line, idx) => (
                    <div key={`pong-${idx}`}>• {line}</div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}
        </section>

        <section className="rounded-2xl border bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">{text.servicesTitle}</h2>
          {hasServicesPreviewOnly ? (
            <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">
              {lang === 'en'
                ? 'Below are service examples from the card. We do not show the total count until the audit confirms it.'
                : lang === 'tr'
                  ? 'Aşağıda karttan alınan hizmet örnekleri var. Denetim toplam sayıyı doğrulamadan bu sayıyı göstermiyoruz.'
                  : lang === 'ar'
                    ? 'في الأسفل أمثلة على الخدمات من البطاقة. لا نعرض العدد الإجمالي حتى يؤكده التدقيق.'
                    : lang === 'el'
                      ? 'Παρακάτω εμφανίζονται παραδείγματα υπηρεσιών από την καταχώριση. Δεν προβάλλουμε συνολικό πλήθος μέχρι να επιβεβαιωθεί από τον έλεγχο.'
                      : 'Ниже показаны примеры услуг из карточки. Общее количество не показываем, пока аудит его не подтвердил.'}
            </div>
          ) : null}
          {services.length > 0 ? (
            <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
              {services.slice(0, 20).map((item, idx) => (
                <div key={`${item.current_name || 'service'}-${idx}`} className="rounded-xl border border-slate-200 p-4">
                  <div className="text-sm text-slate-500">{text.current}</div>
                  <div className="font-medium text-slate-900 mt-1">{item.current_name || text.noDescription}</div>
                  {item.category ? (
                    <div className="mt-1 text-xs text-slate-500">
                      {text.category}: {item.category}
                    </div>
                  ) : null}
                  {item.description ? (
                    <div className="mt-2 text-sm text-slate-600">
                      {item.description}
                    </div>
                  ) : null}
                  {item.improved_name ? (
                    <>
                      <div className="text-sm text-slate-500 mt-3">{text.canShowLikeThis}</div>
                      <div className="font-medium text-sky-700 mt-1">{item.improved_name}</div>
                    </>
                  ) : null}
                  {item.price ? (
                    <div className="mt-2 text-xs font-medium text-slate-700">
                      {text.price}: {item.price}
                    </div>
                  ) : null}
                  {item.source ? <div className="text-xs text-slate-500 mt-2">{text.source}: {item.source}</div> : null}
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
              {text.servicesUnavailable}
            </div>
          )}
        </section>

        {photos.length > 0 ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">{text.photosTitle}</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mt-3">
              {photos.slice(0, 8).map((photo, index) => (
                <img
                  key={`${photo}-${index}`}
                  src={normalizeMediaUrl(photo)}
                  alt={interpolate(text.photoAlt, { index: index + 1 })}
                  className="h-24 w-full rounded-md border border-slate-200 object-cover bg-white"
                />
              ))}
            </div>
          </section>
        ) : null}

        {(reviews.length > 0 || news.length > 0) ? (
          <section className="rounded-2xl border bg-white p-6 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">{text.activityTitle}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-3">
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-semibold text-slate-900">{text.reviews}</div>
                {reviews.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {reviews.slice(0, 3).map((item, idx) => (
                      <div key={`review-${idx}`} className="text-sm text-slate-700 border-b border-slate-100 pb-2">
                        <div className="font-medium flex items-center gap-2">
                          <span>{item.author || text.client}</span>
                          {item.rating ? <span className="text-xs text-amber-600">★ {Number(item.rating).toFixed(1)}</span> : null}
                        </div>
                        {item.text ? <div>{item.text}</div> : null}
                        {item.orgReply ? <div className="mt-1 text-xs text-slate-500">{text.businessReply}: {translateAuditText(lang, item.orgReply)}</div> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 mt-2">{text.freshReviewsMissing}</p>
                )}
              </div>
              <div className="rounded-xl border border-slate-200 p-4">
                <div className="text-sm font-semibold text-slate-900">{text.newsPosts}</div>
                {news.length > 0 ? (
                  <div className="space-y-2 mt-2">
                    {news.slice(0, 3).map((item, idx) => (
                      <div key={`news-${idx}`} className="text-sm text-slate-700 border-b border-slate-100 pb-2">
                        {item.title ? <div className="font-medium">{item.title}</div> : null}
                        {item.text ? <div>{item.text}</div> : null}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500 mt-2">{text.newsMissing}</p>
                )}
              </div>
            </div>
          </section>
        ) : null}

        <section className="rounded-2xl border border-sky-200 bg-sky-50/70 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
            <CircleDollarSign className="w-5 h-5 text-sky-700" />
            {text.nextTitle}
          </h2>
          <p className="text-sm text-slate-700 mt-1">
            {text.nextText}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              className="bg-slate-900 text-white hover:bg-slate-800"
              onClick={() => void startCheckoutFromAudit('starter')}
            >
              Оплатить и открыть кабинет
              <ArrowRight className="w-4 h-4 ml-1" />
            </Button>
            <Button variant="outline" className="border-slate-300" onClick={() => navigate('/login')}>
              {text.optimizeMaps}
            </Button>
            <a href="/contact">
              <Button variant="outline" className="border-slate-300">
                {text.contactExpert}
              </Button>
            </a>
            <a href="https://t.me/Alexdemianov" target="_blank" rel="noreferrer">
              <Button className="bg-sky-600 hover:bg-sky-700 text-white">
                <MessageCircle className="w-4 h-4 mr-1" />
                {text.contactTelegram}
              </Button>
            </a>
            <a href="mailto:info@localos.pro">
                <Button variant="outline">
                  <Mail className="w-4 h-4 mr-1" />
                  {text.contactEmail}
                </Button>
            </a>
            {page.cta?.website ? (
              <a href={page.cta.website} target="_blank" rel="noreferrer">
                <Button variant="outline">
                  <Globe className="w-4 h-4 mr-1" />
                  {text.goToWebsite}
                </Button>
              </a>
            ) : null}
            {page.source_url ? (
              <a href={page.source_url} target="_blank" rel="noreferrer">
                <Button variant="ghost">
                  <ExternalLink className="w-4 h-4 mr-1" />
                  {text.openMapCard}
                </Button>
              </a>
            ) : null}
          </div>
          {page.message ? (
            <div className="mt-4 rounded-xl border border-sky-200 bg-white p-4">
              <div className="text-xs uppercase tracking-wide text-slate-500">{text.firstDraft}</div>
              <div className="text-sm text-slate-800 whitespace-pre-wrap mt-2">{page.message}</div>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
};

export default PublicPartnershipOfferPage;
