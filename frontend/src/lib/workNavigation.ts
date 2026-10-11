import type { Language } from '@/i18n/LanguageContext.logic';

export type WorkGroup = 'daily' | 'directions' | 'control' | 'service';
export type WorkDestination = { id: string; path: string; group: WorkGroup; mobileKey: string; capability?: string };
export const workDestinations: WorkDestination[] = [
  { id: 'today', path: '/dashboard/today', group: 'daily', mobileKey: 'today' },
  { id: 'operator', path: '/dashboard/operator', group: 'daily', mobileKey: 'operator', capability: 'operator' },
  { id: 'maps', path: '/dashboard/card', group: 'directions', mobileKey: 'cards', capability: 'maps' },
  { id: 'content', path: '/dashboard/content', group: 'directions', mobileKey: 'content', capability: 'social_content' },
  { id: 'partnerships', path: '/dashboard/partnerships', group: 'directions', mobileKey: 'partnerships', capability: 'partnerships' },
  { id: 'influencers', path: '/dashboard/influencers', group: 'directions', mobileKey: 'influencers', capability: 'influencers' },
  { id: 'upsells', path: '/dashboard/average-ticket', group: 'directions', mobileKey: 'average_ticket', capability: 'average_ticket' },
  { id: 'automation', path: '/dashboard/agents', group: 'directions', mobileKey: 'agents', capability: 'automation' },
  { id: 'progress', path: '/dashboard/progress', group: 'control', mobileKey: 'progress' },
  { id: 'finance', path: '/dashboard/finance', group: 'control', mobileKey: 'finance', capability: 'finance' },
  { id: 'profile', path: '/dashboard/profile', group: 'service', mobileKey: 'company' },
  { id: 'settings', path: '/dashboard/settings', group: 'service', mobileKey: 'settings' },
  { id: 'more', path: '/dashboard/more', group: 'service', mobileKey: 'more' },
];
const labels: Record<Language, string[]> = {
 ru: ['Сегодня','Управление через чат','Карты и отзывы','Контент','Партнёрства','Инфлюенсеры','Средний чек','ИИ-сотрудники','Результаты','Финансы','Бизнес и команда','Настройки и подключения','Ещё','Ежедневная работа','Направления','Контроль','Служебная область','Меню','Обсудить в чате','Открыть работу','Вернуться к задаче','Выбрать фокус','Источник не указан'],
 en: ['Today','Manage through chat','Maps and reviews','Content','Partnerships','Creators','Average ticket','AI employees','Results','Finance','Business and team','Settings and connections','More','Daily work','Directions','Monitoring','Administration','Menu','Discuss in chat','Open work','Return to task','Choose focus','Source not specified'],
 fr: ['Aujourd’hui','Gérer par chat','Cartes et avis','Contenu','Partenariats','Créateurs','Panier moyen','Employés IA','Résultats','Finances','Entreprise et équipe','Paramètres et connexions','Plus','Travail quotidien','Domaines','Suivi','Administration','Menu','Discuter dans le chat','Ouvrir le travail','Revenir à la tâche','Choisir la priorité','Source non précisée'],
 es: ['Hoy','Gestionar por chat','Mapas y reseñas','Contenido','Alianzas','Creadores','Ticket medio','Empleados IA','Resultados','Finanzas','Negocio y equipo','Ajustes y conexiones','Más','Trabajo diario','Áreas','Seguimiento','Administración','Menú','Hablar por chat','Abrir trabajo','Volver a la tarea','Elegir prioridad','Fuente no indicada'],
 el: ['Σήμερα','Διαχείριση με συνομιλία','Χάρτες και κριτικές','Περιεχόμενο','Συνεργασίες','Δημιουργοί','Μέση απόδειξη','Υπάλληλοι AI','Αποτελέσματα','Οικονομικά','Επιχείρηση και ομάδα','Ρυθμίσεις και συνδέσεις','Περισσότερα','Καθημερινή εργασία','Τομείς','Παρακολούθηση','Διαχείριση','Μενού','Συζήτηση','Άνοιγμα εργασίας','Επιστροφή στην εργασία','Επιλογή προτεραιότητας','Η πηγή δεν ορίστηκε'],
 de: ['Heute','Verwaltung im Chat','Karten und Bewertungen','Inhalte','Partnerschaften','Creators','Durchschnittsbon','KI-Mitarbeiter','Ergebnisse','Finanzen','Unternehmen und Team','Einstellungen und Verbindungen','Mehr','Tägliche Arbeit','Bereiche','Kontrolle','Verwaltung','Menü','Im Chat besprechen','Arbeit öffnen','Zur Aufgabe zurück','Fokus wählen','Quelle nicht angegeben'],
 th: ['วันนี้','จัดการผ่านแชท','แผนที่และรีวิว','เนื้อหา','พันธมิตร','ครีเอเตอร์','ยอดเฉลี่ย','พนักงาน AI','ผลลัพธ์','การเงิน','ธุรกิจและทีม','ตั้งค่าและการเชื่อมต่อ','เพิ่มเติม','งานประจำวัน','ด้านงาน','ติดตาม','การจัดการ','เมนู','คุยในแชท','เปิดงาน','กลับไปที่งาน','เลือกจุดเน้น','ไม่ระบุแหล่งที่มา'],
 ar: ['اليوم','الإدارة بالمحادثة','الخرائط والتقييمات','المحتوى','الشراكات','صناع المحتوى','متوسط الفاتورة','موظفو الذكاء الاصطناعي','النتائج','المالية','النشاط والفريق','الإعدادات والاتصالات','المزيد','العمل اليومي','المجالات','المتابعة','الإدارة','القائمة','ناقش بالمحادثة','افتح العمل','عد إلى المهمة','اختر الأولوية','المصدر غير محدد'],
 ha: ['Yau','Gudanarwa ta hira','Taswira da ra’ayoyi','Abun ciki','Haɗin gwiwa','Masu ƙirƙira','Matsakaicin tikiti','Ma’aikatan AI','Sakamako','Kuɗi','Kasuwanci da ƙungiya','Saituna da haɗi','Ƙari','Aikin yau da kullum','Fannoni','Sa ido','Gudanarwa','Menu','Tattauna a hira','Buɗe aiki','Koma zuwa aiki','Zaɓi fifiko','Ba a bayyana tushe ba'],
 tr: ['Bugün','Sohbetle yönetim','Haritalar ve yorumlar','İçerik','Ortaklıklar','İçerik üreticileri','Ortalama sepet','AI çalışanları','Sonuçlar','Finans','İşletme ve ekip','Ayarlar ve bağlantılar','Diğer','Günlük çalışma','Alanlar','Takip','Yönetim','Menü','Sohbette görüş','Çalışmayı aç','Göreve dön','Öncelik seç','Kaynak belirtilmedi'],
 hy: ['Այսօր','Կառավարում զրույցով','Քարտեզներ և կարծիքներ','Բովանդակություն','Գործընկերություններ','Հեղինակներ','Միջին կտրոն','AI աշխատակիցներ','Արդյունքներ','Ֆինանսներ','Բիզնես և թիմ','Կարգավորումներ և կապեր','Ավելին','Ամենօրյա աշխատանք','Ուղղություններ','Վերահսկում','Կառավարում','Մենյու','Քննարկել զրույցում','Բացել աշխատանքը','Վերադառնալ առաջադրանքին','Ընտրել առաջնահերթություն','Աղբյուրը նշված չէ'],
};
export const workNavigationCopy = (language: Language) => {
 const values = labels[language];
 return { label: (id: string) => values[workDestinations.findIndex(item => item.id === id)] || id,
 groups: { daily: values[13], directions: values[14], control: values[15], service: values[16] },
 menu: values[17], discuss: values[18], open: values[19], back: values[20], focus: values[21], unknownSource: values[22] };
};

export const safeWorkReturn = (value: string | null | undefined): string | null => {
 if (!value || !value.startsWith('/dashboard/') && !value.startsWith('/telegram/control')) return null;
 if (/[\\\r\n]/.test(value) || value.includes('://')) return null;
 const url = new URL(canonicalWorkRoute(value), 'https://localos.pro');
 if (url.origin !== 'https://localos.pro') return null;
 const allowed = [...workDestinations.map(item => item.path), '/dashboard/growth-paths', '/dashboard/work-journal', '/dashboard/chats', '/dashboard/telegram-radar', '/dashboard/web-analytics', '/dashboard/ai-chat-promotion', '/telegram/control'];
 return allowed.some(path => url.pathname === path || url.pathname.startsWith(path + '/')) ? url.pathname + url.search + url.hash : null;
};
export const canonicalWorkRoute = (value: string): string => value.replace('/dashboard/promotion/partnerships', '/dashboard/partnerships').replace('/dashboard/promotion/influencers', '/dashboard/influencers').replace('/dashboard/content-plan', '/dashboard/content');
export const workChatRoute = (route: string, businessId: string, actionId?: string) => {
 const target = new URL(canonicalWorkRoute(route), 'https://localos.pro');
 target.searchParams.set('business_id', businessId);
 const params = new URLSearchParams({ business_id: businessId, work_ref: target.pathname + target.search + target.hash });
 if (actionId) params.set('journey_action', actionId);
 return '/dashboard/operator?' + params;
};
