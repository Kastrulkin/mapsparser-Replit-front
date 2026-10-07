import type { Language } from "@/i18n/LanguageContext";

type MaterialsNavigationItem = {
  name: string;
  description: string;
};

type ContentCopy = {
  materials: string;
  navigation: {
    articles: MaterialsNavigationItem;
    documents: MaterialsNavigationItem;
    cases: MaterialsNavigationItem;
    documentation: MaterialsNavigationItem;
  };
  articles: {
    eyebrow: string;
    title: string;
    description: string;
    latest: string;
    chooseTopic: string;
    all: string;
    back: string;
    seoTitle: string;
    seoDescription: string;
  };
  shared: {
    readMore: string;
    related: string;
    ctaTitle: string;
    ctaDescription: string;
    audit: string;
    discuss: string;
    loading: string;
  };
};

export const contentCopy: Record<Language, ContentCopy> = {
  ru: {
    materials: "Материалы",
    navigation: {
      articles: { name: "Статьи", description: "Карты, отзывы и работа локального бизнеса" },
      documents: { name: "Документы", description: "Чек-листы, шаблоны и таблицы" },
      cases: { name: "Кейсы", description: "Что уже изменилось у владельцев бизнеса" },
      documentation: { name: "Документация", description: "LocalOS для пользователей, API и ИИ-агентов" },
    },
    articles: {
      eyebrow: "Материалы LocalOS",
      title: "Статьи о бизнесе, клиентах и росте",
      description: "Практические разборы о картах, отзывах, клиентах, финансах и ежедневной работе владельца.",
      latest: "Последние статьи",
      chooseTopic: "Выберите тему и начните с самого практичного материала.",
      all: "Все",
      back: "Назад к статьям",
      seoTitle: "Статьи для владельцев локального бизнеса — LocalOS",
      seoDescription: "Статьи LocalOS о картах, отзывах, клиентах, финансах и автоматизации регулярной работы локального бизнеса.",
    },
    shared: {
      readMore: "Читать дальше",
      related: "Читайте также",
      ctaTitle: "Хотите понять, какую работу можно передать LocalOS?",
      ctaDescription: "Начните с бесплатного аудита карточки. Покажем, что мешает клиентам найти и выбрать вас.",
      audit: "Получить бесплатный аудит",
      discuss: "Обсудить внедрение",
      loading: "Загружаем статью…",
    },
  },
  en: {
    materials: "Resources",
    navigation: {
      articles: { name: "Articles", description: "Maps, reviews, and running a local business" },
      documents: { name: "Documents", description: "Checklists, templates, and spreadsheets" },
      cases: { name: "Case studies", description: "What business owners have already changed" },
      documentation: { name: "Documentation", description: "LocalOS for users, APIs, and AI agents" },
    },
    articles: { eyebrow: "LocalOS resources", title: "Articles about business, customers, and growth", description: "Practical guides to maps, reviews, customers, finance, and an owner's daily work.", latest: "Latest articles", chooseTopic: "Choose a topic and start with the most useful guide.", all: "All", back: "Back to articles", seoTitle: "Articles for local business owners — LocalOS", seoDescription: "LocalOS articles about maps, reviews, customers, finance, and automating recurring work in a local business." },
    shared: { readMore: "Read more", related: "Related reading", ctaTitle: "Want to see what work you can hand over to LocalOS?", ctaDescription: "Start with a free listing audit. We will show what prevents customers from finding and choosing you.", audit: "Get a free audit", discuss: "Discuss implementation", loading: "Loading article…" },
  },
  fr: {
    materials: "Ressources",
    navigation: {
      articles: { name: "Articles", description: "Cartes, avis et gestion d'une entreprise locale" },
      documents: { name: "Documents", description: "Listes de contrôle, modèles et tableaux" },
      cases: { name: "Cas clients", description: "Ce que des dirigeants ont déjà amélioré" },
      documentation: { name: "Documentation", description: "LocalOS pour les utilisateurs, les API et les agents IA" },
    },
    articles: { eyebrow: "Ressources LocalOS", title: "Articles sur l'entreprise, les clients et la croissance", description: "Des guides pratiques sur les cartes, les avis, les clients, les finances et le quotidien du dirigeant.", latest: "Derniers articles", chooseTopic: "Choisissez un thème et commencez par le guide le plus utile.", all: "Tous", back: "Retour aux articles", seoTitle: "Articles pour les dirigeants d'entreprises locales — LocalOS", seoDescription: "Articles LocalOS sur les cartes, les avis, les clients, les finances et l'automatisation du travail récurrent." },
    shared: { readMore: "Lire la suite", related: "À lire aussi", ctaTitle: "Vous voulez savoir quelles tâches confier à LocalOS ?", ctaDescription: "Commencez par un audit gratuit de votre fiche. Nous montrerons ce qui empêche les clients de vous trouver et de vous choisir.", audit: "Obtenir un audit gratuit", discuss: "Parler du déploiement", loading: "Chargement de l'article…" },
  },
  es: {
    materials: "Recursos",
    navigation: {
      articles: { name: "Artículos", description: "Mapas, reseñas y gestión de un negocio local" },
      documents: { name: "Documentos", description: "Listas de control, plantillas y tablas" },
      cases: { name: "Casos", description: "Lo que otros propietarios ya han mejorado" },
      documentation: { name: "Documentación", description: "LocalOS para usuarios, API y agentes de IA" },
    },
    articles: { eyebrow: "Recursos de LocalOS", title: "Artículos sobre negocio, clientes y crecimiento", description: "Guías prácticas sobre mapas, reseñas, clientes, finanzas y el trabajo diario del propietario.", latest: "Últimos artículos", chooseTopic: "Elige un tema y empieza por la guía más útil.", all: "Todos", back: "Volver a los artículos", seoTitle: "Artículos para propietarios de negocios locales — LocalOS", seoDescription: "Artículos de LocalOS sobre mapas, reseñas, clientes, finanzas y automatización del trabajo recurrente." },
    shared: { readMore: "Leer más", related: "También te puede interesar", ctaTitle: "¿Quieres saber qué trabajo puedes delegar en LocalOS?", ctaDescription: "Empieza con una auditoría gratuita de tu ficha. Te mostraremos qué impide que los clientes te encuentren y te elijan.", audit: "Obtener auditoría gratuita", discuss: "Hablar de la implementación", loading: "Cargando artículo…" },
  },
  el: {
    materials: "Πόροι",
    navigation: {
      articles: { name: "Άρθρα", description: "Χάρτες, κριτικές και καθημερινή λειτουργία μιας τοπικής επιχείρησης" },
      documents: { name: "Εργαλεία", description: "Λίστες ελέγχου, πρότυπα και πίνακες εργασίας" },
      cases: { name: "Παραδείγματα", description: "Πραγματικές αλλαγές σε τοπικές επιχειρήσεις" },
      documentation: { name: "Τεκμηρίωση", description: "LocalOS για χρήστες, API και πράκτορες τεχνητής νοημοσύνης" },
    },
    articles: { eyebrow: "Πόροι LocalOS", title: "Άρθρα για την επιχείρηση, τους πελάτες και την ανάπτυξη", description: "Πρακτικοί οδηγοί για το επαγγελματικό προφίλ στους χάρτες, τις κριτικές, τους πελάτες, τα οικονομικά και την καθημερινή εργασία του ιδιοκτήτη.", latest: "Νέα άρθρα", chooseTopic: "Επιλέξτε θέμα και ξεκινήστε από τον οδηγό που σας είναι πιο χρήσιμος.", all: "Όλα", back: "Επιστροφή στα άρθρα", seoTitle: "Άρθρα για ιδιοκτήτες τοπικών επιχειρήσεων — LocalOS", seoDescription: "Άρθρα του LocalOS για χάρτες, κριτικές, πελάτες, οικονομικά και αυτοματοποίηση επαναλαμβανόμενων εργασιών." },
    shared: { readMore: "Διαβάστε περισσότερα", related: "Δείτε επίσης", ctaTitle: "Θέλετε να δείτε ποιες εργασίες μπορείτε να αναθέσετε στο LocalOS;", ctaDescription: "Ξεκινήστε με δωρεάν έλεγχο του επαγγελματικού σας προφίλ. Θα σας δείξουμε τι δυσκολεύει τους πελάτες να σας βρουν και να σας επιλέξουν.", audit: "Δωρεάν έλεγχος", discuss: "Συζητήστε την εφαρμογή", loading: "Το άρθρο φορτώνεται…" },
  },
  de: {
    materials: "Wissen",
    navigation: {
      articles: { name: "Artikel", description: "Karten, Bewertungen und lokale Betriebsführung" },
      documents: { name: "Dokumente", description: "Checklisten, Vorlagen und Tabellen" },
      cases: { name: "Fallstudien", description: "Was andere Inhaber bereits verbessert haben" },
      documentation: { name: "Dokumentation", description: "LocalOS für Nutzer, APIs und KI-Agenten" },
    },
    articles: { eyebrow: "LocalOS Wissen", title: "Artikel über Unternehmen, Kunden und Wachstum", description: "Praxisnahe Leitfäden zu Karten, Bewertungen, Kunden, Finanzen und dem Alltag von Inhabern.", latest: "Neueste Artikel", chooseTopic: "Wählen Sie ein Thema und beginnen Sie mit dem nützlichsten Leitfaden.", all: "Alle", back: "Zurück zu den Artikeln", seoTitle: "Artikel für Inhaber lokaler Unternehmen — LocalOS", seoDescription: "LocalOS Artikel über Karten, Bewertungen, Kunden, Finanzen und die Automatisierung wiederkehrender Arbeit." },
    shared: { readMore: "Weiterlesen", related: "Auch interessant", ctaTitle: "Möchten Sie wissen, welche Arbeit LocalOS übernehmen kann?", ctaDescription: "Starten Sie mit einem kostenlosen Eintragsaudit. Wir zeigen, was Kunden daran hindert, Sie zu finden und auszuwählen.", audit: "Kostenloses Audit", discuss: "Einführung besprechen", loading: "Artikel wird geladen…" },
  },
  th: {
    materials: "แหล่งความรู้",
    navigation: {
      articles: { name: "บทความ", description: "แผนที่ รีวิว และการบริหารธุรกิจท้องถิ่น" },
      documents: { name: "เอกสาร", description: "เช็กลิสต์ เทมเพลต และตาราง" },
      cases: { name: "กรณีศึกษา", description: "สิ่งที่เจ้าของธุรกิจรายอื่นปรับปรุงแล้ว" },
      documentation: { name: "คู่มือการใช้งาน", description: "LocalOS สำหรับผู้ใช้ API และเอเจนต์ AI" },
    },
    articles: { eyebrow: "แหล่งความรู้ LocalOS", title: "บทความเรื่องธุรกิจ ลูกค้า และการเติบโต", description: "คู่มือเชิงปฏิบัติเกี่ยวกับแผนที่ รีวิว ลูกค้า การเงิน และงานประจำวันของเจ้าของธุรกิจ", latest: "บทความล่าสุด", chooseTopic: "เลือกหัวข้อแล้วเริ่มจากคู่มือที่ใช้งานได้จริงที่สุด", all: "ทั้งหมด", back: "กลับไปที่บทความ", seoTitle: "บทความสำหรับเจ้าของธุรกิจท้องถิ่น — LocalOS", seoDescription: "บทความ LocalOS เกี่ยวกับแผนที่ รีวิว ลูกค้า การเงิน และการทำงานซ้ำให้เป็นอัตโนมัติ" },
    shared: { readMore: "อ่านต่อ", related: "อ่านเพิ่มเติม", ctaTitle: "อยากรู้ว่างานใดส่งต่อให้ LocalOS ได้บ้าง", ctaDescription: "เริ่มด้วยการตรวจสอบข้อมูลธุรกิจฟรี เราจะแสดงสิ่งที่ทำให้ลูกค้าหาคุณไม่เจอหรือไม่เลือกคุณ", audit: "รับการตรวจสอบฟรี", discuss: "พูดคุยการติดตั้ง", loading: "กำลังโหลดบทความ…" },
  },
  ar: {
    materials: "الموارد",
    navigation: {
      articles: { name: "المقالات", description: "الخرائط والتقييمات وإدارة الأعمال المحلية" },
      documents: { name: "المستندات", description: "قوائم التحقق والقوالب والجداول" },
      cases: { name: "دراسات الحالة", description: "ما حسّنه أصحاب الأعمال بالفعل" },
      documentation: { name: "التوثيق", description: "LocalOS للمستخدمين وواجهات API ووكلاء الذكاء الاصطناعي" },
    },
    articles: { eyebrow: "موارد LocalOS", title: "مقالات عن الأعمال والعملاء والنمو", description: "أدلة عملية عن الخرائط والتقييمات والعملاء والمال والعمل اليومي لصاحب العمل.", latest: "أحدث المقالات", chooseTopic: "اختر موضوعًا وابدأ بالدليل الأكثر فائدة.", all: "الكل", back: "العودة إلى المقالات", seoTitle: "مقالات لأصحاب الأعمال المحلية — LocalOS", seoDescription: "مقالات LocalOS عن الخرائط والتقييمات والعملاء والمال وأتمتة العمل المتكرر." },
    shared: { readMore: "اقرأ المزيد", related: "اقرأ أيضًا", ctaTitle: "هل تريد معرفة العمل الذي يمكن أن يتولاه LocalOS؟", ctaDescription: "ابدأ بتدقيق مجاني لبطاقة نشاطك. سنوضح ما يمنع العملاء من العثور عليك واختيارك.", audit: "احصل على تدقيق مجاني", discuss: "ناقش التطبيق", loading: "جارٍ تحميل المقال…" },
  },
  ha: {
    materials: "Albarkatu",
    navigation: {
      articles: { name: "Kasidu", description: "Taswirori, bita da tafiyar da kasuwancin gida" },
      documents: { name: "Takardu", description: "Jerin dubawa, samfura da tebura" },
      cases: { name: "Misalan aiki", description: "Abin da sauran masu kasuwanci suka riga suka inganta" },
      documentation: { name: "Takardun bayani", description: "LocalOS ga masu amfani, API da wakilan AI" },
    },
    articles: { eyebrow: "Albarkatun LocalOS", title: "Kasidu kan kasuwanci, kwastomomi da bunƙasa", description: "Jagorori masu amfani kan taswirori, bita, kwastomomi, kuɗi da aikin yau da kullum na mai kasuwanci.", latest: "Sabbin kasidu", chooseTopic: "Zaɓi batu ka fara da jagora mafi amfani.", all: "Duka", back: "Koma kasidu", seoTitle: "Kasidu ga masu kasuwancin gida — LocalOS", seoDescription: "Kasidun LocalOS kan taswirori, bita, kwastomomi, kuɗi da sarrafa ayyukan da ake maimaitawa." },
    shared: { readMore: "Kara karantawa", related: "Karanta kuma", ctaTitle: "Kana son sanin ayyukan da LocalOS zai iya ɗauka?", ctaDescription: "Fara da duba bayanan kasuwancinka kyauta. Za mu nuna abin da ke hana kwastomomi samunka da zaɓenka.", audit: "Samu dubawa kyauta", discuss: "Tattauna aiwatarwa", loading: "Ana loda kasida…" },
  },
  tr: {
    materials: "Kaynaklar",
    navigation: {
      articles: { name: "Makaleler", description: "Haritalar, yorumlar ve yerel işletme yönetimi" },
      documents: { name: "Çalışma araçları", description: "Kontrol listeleri, şablonlar ve tablolar" },
      cases: { name: "Uygulama örnekleri", description: "İşletme sahiplerinin elde ettiği sonuçlar" },
      documentation: { name: "Dokümantasyon", description: "Kullanıcılar, API'ler ve yapay zekâ asistanları için LocalOS" },
    },
    articles: { eyebrow: "LocalOS kaynakları", title: "İşletme, müşteriler ve büyüme üzerine makaleler", description: "Haritalardaki işletme profilleri, yorumlar, müşteriler, finans ve işletme sahibinin günlük işleri için pratik rehberler.", latest: "Yeni makaleler", chooseTopic: "Konunuzu seçin ve size en faydalı rehberden başlayın.", all: "Tümü", back: "Makalelere dön", seoTitle: "Yerel işletme sahipleri için makaleler — LocalOS", seoDescription: "Haritalar, yorumlar, müşteriler, finans ve tekrarlanan işlerin otomasyonu hakkında LocalOS makaleleri." },
    shared: { readMore: "Devamını okuyun", related: "Bunlara da göz atın", ctaTitle: "LocalOS'a hangi işleri devredebileceğinizi görmek ister misiniz?", ctaDescription: "Ücretsiz işletme profili kontrolüyle başlayın. Müşterilerin sizi bulmasını ve seçmesini zorlaştıran noktaları gösterelim.", audit: "Ücretsiz kontrol alın", discuss: "Uygulamayı görüşün", loading: "Makale yükleniyor…" },
  },
};
