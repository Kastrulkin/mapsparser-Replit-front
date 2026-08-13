import type { Language } from "@/i18n/LanguageContext";

type CollectionCopy = {
  all: string;
  documents: {
    eyebrow: string;
    title: string;
    description: string;
    library: string;
    libraryDescription: string;
    back: string;
    inside: string;
    seoTitle: string;
    seoDescription: string;
  };
  cases: {
    eyebrow: string;
    title: string;
    description: string;
    library: string;
    libraryDescription: string;
    back: string;
    situation: string;
    actions: string;
    result: string;
    seoTitle: string;
    seoDescription: string;
  };
};

export const collectionCopy: Record<Language, CollectionCopy> = {
  ru: {
    all: "Все",
    documents: { eyebrow: "Практические материалы", title: "Документы для управления ростом локального бизнеса", description: "Готовые материалы, которые можно использовать в работе: чек-листы аудита, шаблоны ответов, таблицы контроля и инструкции.", library: "Библиотека документов", libraryDescription: "Не статьи, а рабочие заготовки для команды и собственника.", back: "Назад к документам", inside: "Что внутри", seoTitle: "Документы для локального маркетинга — LocalOS", seoDescription: "Прикладные документы LocalOS: чек-листы, шаблоны, таблицы и инструкции для управления локальным маркетингом." },
    cases: { eyebrow: "Результаты LocalOS", title: "Кейсы: как локальный бизнес получает больше заявок", description: "Истории роста в формате проблема, действия и результат: что изменили в картах, отзывах и коммуникации с клиентами.", library: "Разборы внедрений", libraryDescription: "Смотрите на цифры, действия и контекст, а не на красивые обещания.", back: "Назад к кейсам", situation: "Исходная ситуация", actions: "Что сделали", result: "Результат", seoTitle: "Кейсы локального бизнеса — LocalOS", seoDescription: "Кейсы LocalOS о росте заявок, отзывов, записей и повторных клиентов для салонов, кафе и локального бизнеса." },
  },
  en: {
    all: "All",
    documents: { eyebrow: "Practical resources", title: "Documents for running and growing a local business", description: "Ready-to-use audit checklists, response templates, tracking tables, and instructions.", library: "Document library", libraryDescription: "Working resources for owners and teams, not general articles.", back: "Back to documents", inside: "What is inside", seoTitle: "Local business documents — LocalOS", seoDescription: "Practical LocalOS checklists, templates, tables, and instructions for local businesses." },
    cases: { eyebrow: "LocalOS results", title: "Case studies: how local businesses get more enquiries", description: "The starting point, the work completed, and the measured result for maps, reviews, and customer communication.", library: "Implementation stories", libraryDescription: "Look at the numbers, actions, and context — not polished promises.", back: "Back to case studies", situation: "Starting point", actions: "What we did", result: "Result", seoTitle: "Local business case studies — LocalOS", seoDescription: "LocalOS case studies about enquiries, reviews, bookings, and repeat customers." },
  },
  fr: {
    all: "Tous",
    documents: { eyebrow: "Ressources pratiques", title: "Documents pour piloter la croissance d’une entreprise locale", description: "Listes de contrôle, modèles de réponses, tableaux de suivi et instructions prêts à l’emploi.", library: "Bibliothèque de documents", libraryDescription: "Des outils de travail pour le dirigeant et son équipe.", back: "Retour aux documents", inside: "Contenu", seoTitle: "Documents pour entreprises locales — LocalOS", seoDescription: "Listes de contrôle, modèles et tableaux pratiques de LocalOS." },
    cases: { eyebrow: "Résultats LocalOS", title: "Cas clients : comment les entreprises locales obtiennent plus de demandes", description: "La situation initiale, les actions menées et les résultats obtenus sur les cartes, les avis et la relation client.", library: "Retours d’expérience", libraryDescription: "Des chiffres, des actions et du contexte, sans promesses creuses.", back: "Retour aux cas clients", situation: "Situation initiale", actions: "Actions menées", result: "Résultat", seoTitle: "Cas clients d’entreprises locales — LocalOS", seoDescription: "Cas LocalOS sur les demandes, les avis, les réservations et les clients récurrents." },
  },
  es: {
    all: "Todos",
    documents: { eyebrow: "Recursos prácticos", title: "Documentos para gestionar el crecimiento de un negocio local", description: "Listas de control, plantillas de respuesta, tablas de seguimiento e instrucciones listas para usar.", library: "Biblioteca de documentos", libraryDescription: "Material de trabajo para propietarios y equipos.", back: "Volver a documentos", inside: "Qué incluye", seoTitle: "Documentos para negocios locales — LocalOS", seoDescription: "Listas de control, plantillas y tablas prácticas de LocalOS." },
    cases: { eyebrow: "Resultados de LocalOS", title: "Casos: cómo los negocios locales consiguen más solicitudes", description: "La situación inicial, el trabajo realizado y el resultado en mapas, reseñas y comunicación con clientes.", library: "Casos de implementación", libraryDescription: "Cifras, acciones y contexto, sin promesas vacías.", back: "Volver a casos", situation: "Situación inicial", actions: "Qué hicimos", result: "Resultado", seoTitle: "Casos de negocios locales — LocalOS", seoDescription: "Casos de LocalOS sobre solicitudes, reseñas, reservas y clientes recurrentes." },
  },
  el: {
    all: "Όλα",
    documents: { eyebrow: "Πρακτικά εργαλεία", title: "Εργαλεία για την καθημερινή διαχείριση μιας τοπικής επιχείρησης", description: "Έτοιμες λίστες ελέγχου, πρότυπα απαντήσεων, πίνακες παρακολούθησης και οδηγίες.", library: "Βιβλιοθήκη εργαλείων", libraryDescription: "Υλικό εργασίας για ιδιοκτήτες και ομάδες.", back: "Επιστροφή στα εργαλεία", inside: "Τι περιλαμβάνει", seoTitle: "Πρακτικά εργαλεία για τοπικές επιχειρήσεις — LocalOS", seoDescription: "Λίστες ελέγχου, πρότυπα και πίνακες του LocalOS για καθημερινή χρήση." },
    cases: { eyebrow: "Αποτελέσματα με το LocalOS", title: "Παραδείγματα: πώς οι τοπικές επιχειρήσεις κερδίζουν περισσότερους πελάτες", description: "Η αρχική κατάσταση, οι ενέργειες και το αποτέλεσμα στο επαγγελματικό προφίλ, στις κριτικές και στην επικοινωνία με τους πελάτες.", library: "Παραδείγματα εφαρμογής", libraryDescription: "Αριθμοί, ενέργειες και πραγματικό πλαίσιο — χωρίς αόριστες υποσχέσεις.", back: "Επιστροφή στα παραδείγματα", situation: "Αρχική κατάσταση", actions: "Τι κάναμε", result: "Αποτέλεσμα", seoTitle: "Παραδείγματα τοπικών επιχειρήσεων — LocalOS", seoDescription: "Παραδείγματα εφαρμογής του LocalOS για αιτήματα, κριτικές, κρατήσεις και πελάτες που επιστρέφουν." },
  },
  de: {
    all: "Alle",
    documents: { eyebrow: "Praktische Materialien", title: "Dokumente für die Steuerung eines lokalen Unternehmens", description: "Einsatzbereite Audit-Checklisten, Antwortvorlagen, Kontrolltabellen und Anleitungen.", library: "Dokumentenbibliothek", libraryDescription: "Arbeitsmaterialien für Inhaber und Teams.", back: "Zurück zu den Dokumenten", inside: "Inhalt", seoTitle: "Dokumente für lokale Unternehmen — LocalOS", seoDescription: "Praktische LocalOS Checklisten, Vorlagen und Tabellen." },
    cases: { eyebrow: "LocalOS Ergebnisse", title: "Fallstudien: Wie lokale Unternehmen mehr Anfragen erhalten", description: "Ausgangslage, umgesetzte Maßnahmen und Ergebnisse bei Karten, Bewertungen und Kundenkommunikation.", library: "Umsetzungsbeispiele", libraryDescription: "Zahlen, Maßnahmen und Kontext statt leerer Versprechen.", back: "Zurück zu den Fallstudien", situation: "Ausgangslage", actions: "Was wir getan haben", result: "Ergebnis", seoTitle: "Fallstudien lokaler Unternehmen — LocalOS", seoDescription: "LocalOS Fallstudien zu Anfragen, Bewertungen, Buchungen und Stammkunden." },
  },
  th: {
    all: "ทั้งหมด",
    documents: { eyebrow: "สื่อใช้งานจริง", title: "เอกสารสำหรับบริหารการเติบโตของธุรกิจท้องถิ่น", description: "เช็กลิสต์ตรวจสอบ เทมเพลตคำตอบ ตารางติดตาม และคำแนะนำที่พร้อมใช้งาน", library: "คลังเอกสาร", libraryDescription: "เครื่องมือทำงานสำหรับเจ้าของและทีม", back: "กลับไปที่เอกสาร", inside: "เนื้อหาภายใน", seoTitle: "เอกสารสำหรับธุรกิจท้องถิ่น — LocalOS", seoDescription: "เช็กลิสต์ เทมเพลต และตารางใช้งานจริงจาก LocalOS" },
    cases: { eyebrow: "ผลลัพธ์จาก LocalOS", title: "กรณีศึกษา: ธุรกิจท้องถิ่นเพิ่มคำขอจากลูกค้าได้อย่างไร", description: "สถานการณ์เริ่มต้น งานที่ทำ และผลลัพธ์จากแผนที่ รีวิว และการสื่อสารกับลูกค้า", library: "กรณีการใช้งาน", libraryDescription: "ดูตัวเลข การลงมือทำ และบริบท แทนคำสัญญาสวยหรู", back: "กลับไปที่กรณีศึกษา", situation: "สถานการณ์เริ่มต้น", actions: "สิ่งที่ทำ", result: "ผลลัพธ์", seoTitle: "กรณีศึกษาธุรกิจท้องถิ่น — LocalOS", seoDescription: "กรณีศึกษา LocalOS เรื่องคำขอ รีวิว การจอง และลูกค้าที่กลับมา" },
  },
  ar: {
    all: "الكل",
    documents: { eyebrow: "مواد عملية", title: "مستندات لإدارة نمو النشاط المحلي", description: "قوائم تدقيق وقوالب ردود وجداول متابعة وتعليمات جاهزة للاستخدام.", library: "مكتبة المستندات", libraryDescription: "أدوات عمل لأصحاب الأنشطة والفرق.", back: "العودة إلى المستندات", inside: "المحتوى", seoTitle: "مستندات للأعمال المحلية — LocalOS", seoDescription: "قوائم تدقيق وقوالب وجداول عملية من LocalOS." },
    cases: { eyebrow: "نتائج LocalOS", title: "دراسات حالة: كيف تحصل الأعمال المحلية على طلبات أكثر", description: "الوضع الأولي والعمل المنجز والنتيجة في الخرائط والتقييمات والتواصل مع العملاء.", library: "تجارب التطبيق", libraryDescription: "أرقام وإجراءات وسياق بدل الوعود المنمقة.", back: "العودة إلى دراسات الحالة", situation: "الوضع الأولي", actions: "ما قمنا به", result: "النتيجة", seoTitle: "دراسات حالة للأعمال المحلية — LocalOS", seoDescription: "دراسات LocalOS عن الطلبات والتقييمات والحجوزات والعملاء المتكررين." },
  },
  ha: {
    all: "Duka",
    documents: { eyebrow: "Kayan aiki", title: "Takardu don tafiyar da bunƙasar kasuwancin gida", description: "Jerin dubawa, samfuran amsa, teburan sa ido da umarni da aka shirya amfani da su.", library: "Rumbun takardu", libraryDescription: "Kayan aiki ga masu kasuwanci da ƙungiyoyi.", back: "Koma takardu", inside: "Abin da ke ciki", seoTitle: "Takardu ga kasuwancin gida — LocalOS", seoDescription: "Jerin dubawa, samfura da teburan LocalOS masu amfani." },
    cases: { eyebrow: "Sakamakon LocalOS", title: "Misalan aiki: yadda kasuwancin gida ke samun ƙarin buƙatu", description: "Matsayin farko, aikin da aka yi da sakamakon taswirori, bita da sadarwar kwastomomi.", library: "Misalan aiwatarwa", libraryDescription: "Lambobi, ayyuka da yanayi maimakon alkawura marasa tushe.", back: "Koma misalan aiki", situation: "Matsayin farko", actions: "Abin da muka yi", result: "Sakamako", seoTitle: "Misalan kasuwancin gida — LocalOS", seoDescription: "Misalan LocalOS kan buƙatu, bita, ajiyar lokaci da kwastomomi masu dawowa." },
  },
  tr: {
    all: "Tümü",
    documents: { eyebrow: "Pratik çalışma araçları", title: "Yerel işletmenin günlük yönetimi için araçlar", description: "Hemen kullanabileceğiniz kontrol listeleri, yanıt şablonları ve takip tabloları.", library: "Çalışma araçları", libraryDescription: "İşletme sahipleri ve ekipler için hazır araçlar.", back: "Araçlara dön", inside: "İçindekiler", seoTitle: "Yerel işletmeler için çalışma araçları — LocalOS", seoDescription: "LocalOS'un yerel işletmeler için hazırladığı kontrol listeleri, şablonlar ve takip tabloları." },
    cases: { eyebrow: "LocalOS sonuçları", title: "Uygulama örnekleri: yerel işletmeler nasıl daha fazla müşteri kazanıyor", description: "Sorun, yapılan çalışma ve sonuç: haritalarda, yorumlarda ve müşteri iletişiminde nelerin değiştiğini görün.", library: "Uygulama örnekleri", libraryDescription: "Gösterişli vaatler yerine rakamlar, yapılan işler ve gerçek bağlam.", back: "Uygulama örneklerine dön", situation: "Başlangıç durumu", actions: "Neler yaptık", result: "Sonuç", seoTitle: "Yerel işletme uygulama örnekleri — LocalOS", seoDescription: "LocalOS'un müşteri talepleri, yorumlar, rezervasyonlar ve tekrar gelen müşteriler üzerine uygulama örnekleri." },
  },
};
