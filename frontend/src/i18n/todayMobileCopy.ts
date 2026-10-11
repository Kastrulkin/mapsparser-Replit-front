import type { Language } from './LanguageContext.logic';

export type TodayPreferredFlow = 'content' | 'maps' | 'influencers' | 'partnerships' | 'upsells' | 'automation';

type TodayMobileCopy = {
  preferredLabels: Record<TodayPreferredFlow, string>;
  preferredFallbackReason: string;
  preferredContentCta: string;
  preferredGeneralCta: string;
  urgentCta: string;
  preferredHint: string;
  noTasksEyebrow: string;
  emptyTitle: string;
  emptyNetworkReason: string;
  emptyReason: string;
  openPlatformQueue: string;
  openGrowthPlan: string;
};

const copy: Record<Language, TodayMobileCopy> = {
  ru: {
    preferredLabels: { content: 'Контент-план', maps: 'Карты и отзывы', influencers: 'Работа с авторами', partnerships: 'Партнёрства', upsells: 'Продажи и средний чек', automation: 'ИИ-сотрудники' },
    preferredFallbackReason: 'Откройте выбранное направление и продолжите работу.', preferredContentCta: 'Открыть контент-план', preferredGeneralCta: 'Продолжить работу', urgentCta: 'Разобрать задачу', preferredHint: 'Ваше выбранное направление работы.', noTasksEyebrow: 'Новых задач нет', emptyTitle: 'Сегодня от вас ничего не требуется', emptyNetworkReason: 'По точкам сети нет задач, которые сейчас требуют вашего решения.', emptyReason: 'По последним загруженным данным новых задач для вас нет.', openPlatformQueue: 'Открыть очередь платформы', openGrowthPlan: 'Открыть план роста',
  },
  en: {
    preferredLabels: { content: 'Content plan', maps: 'Maps and reviews', influencers: 'Creator work', partnerships: 'Partnerships', upsells: 'Sales and average ticket', automation: 'AI employees' },
    preferredFallbackReason: 'Open the selected area and continue working.', preferredContentCta: 'Open content plan', preferredGeneralCta: 'Continue working', urgentCta: 'Review task', preferredHint: 'Your selected work area.', noTasksEyebrow: 'No new tasks', emptyTitle: 'Nothing needs your attention today', emptyNetworkReason: 'No network locations currently need your decision.', emptyReason: 'There are no new tasks for you in the latest uploaded data.', openPlatformQueue: 'Open platform queue', openGrowthPlan: 'Open growth plan',
  },
  fr: {
    preferredLabels: { content: 'Plan de contenu', maps: 'Cartes et avis', influencers: 'Travail avec les créateurs', partnerships: 'Partenariats', upsells: 'Ventes et panier moyen', automation: 'Employés IA' },
    preferredFallbackReason: 'Ouvrez le domaine choisi et poursuivez votre travail.', preferredContentCta: 'Ouvrir le plan de contenu', preferredGeneralCta: 'Continuer le travail', urgentCta: 'Examiner la tâche', preferredHint: 'Votre domaine de travail choisi.', noTasksEyebrow: 'Aucune nouvelle tâche', emptyTitle: 'Rien ne requiert votre attention aujourd’hui', emptyNetworkReason: 'Aucun point du réseau ne requiert actuellement votre décision.', emptyReason: 'Les dernières données chargées ne contiennent aucune nouvelle tâche pour vous.', openPlatformQueue: 'Ouvrir la file de la plateforme', openGrowthPlan: 'Ouvrir le plan de croissance',
  },
  es: {
    preferredLabels: { content: 'Plan de contenido', maps: 'Mapas y reseñas', influencers: 'Trabajo con creadores', partnerships: 'Colaboraciones', upsells: 'Ventas y ticket medio', automation: 'Empleados de IA' },
    preferredFallbackReason: 'Abre el área seleccionada y continúa trabajando.', preferredContentCta: 'Abrir plan de contenido', preferredGeneralCta: 'Continuar trabajando', urgentCta: 'Resolver tarea', preferredHint: 'Tu área de trabajo seleccionada.', noTasksEyebrow: 'No hay tareas nuevas', emptyTitle: 'Hoy no necesitas hacer nada', emptyNetworkReason: 'Ninguna ubicación de la red requiere ahora tu decisión.', emptyReason: 'No hay tareas nuevas para ti en los últimos datos cargados.', openPlatformQueue: 'Abrir cola de la plataforma', openGrowthPlan: 'Abrir plan de crecimiento',
  },
  el: {
    preferredLabels: { content: 'Πλάνο περιεχομένου', maps: 'Χάρτες και κριτικές', influencers: 'Συνεργασία με δημιουργούς', partnerships: 'Συνεργασίες', upsells: 'Πωλήσεις και μέση αξία', automation: 'Υπάλληλοι AI' },
    preferredFallbackReason: 'Ανοίξτε τον επιλεγμένο τομέα και συνεχίστε την εργασία.', preferredContentCta: 'Άνοιγμα πλάνου περιεχομένου', preferredGeneralCta: 'Συνέχιση εργασίας', urgentCta: 'Εξέταση εργασίας', preferredHint: 'Ο επιλεγμένος τομέας εργασίας σας.', noTasksEyebrow: 'Δεν υπάρχουν νέες εργασίες', emptyTitle: 'Δεν χρειάζεται κάτι από εσάς σήμερα', emptyNetworkReason: 'Κανένα σημείο του δικτύου δεν χρειάζεται τώρα την απόφασή σας.', emptyReason: 'Δεν υπάρχουν νέες εργασίες για εσάς στα τελευταία δεδομένα.', openPlatformQueue: 'Άνοιγμα ουράς πλατφόρμας', openGrowthPlan: 'Άνοιγμα πλάνου ανάπτυξης',
  },
  de: {
    preferredLabels: { content: 'Inhaltsplan', maps: 'Karten und Bewertungen', influencers: 'Arbeit mit Creators', partnerships: 'Partnerschaften', upsells: 'Verkäufe und Durchschnittsbon', automation: 'KI-Mitarbeiter' },
    preferredFallbackReason: 'Öffnen Sie den ausgewählten Bereich und arbeiten Sie weiter.', preferredContentCta: 'Inhaltsplan öffnen', preferredGeneralCta: 'Weiterarbeiten', urgentCta: 'Aufgabe prüfen', preferredHint: 'Ihr ausgewählter Arbeitsbereich.', noTasksEyebrow: 'Keine neuen Aufgaben', emptyTitle: 'Heute ist nichts von Ihnen erforderlich', emptyNetworkReason: 'Kein Standort im Netzwerk benötigt derzeit Ihre Entscheidung.', emptyReason: 'In den zuletzt geladenen Daten gibt es keine neuen Aufgaben für Sie.', openPlatformQueue: 'Plattformwarteschlange öffnen', openGrowthPlan: 'Wachstumsplan öffnen',
  },
  th: {
    preferredLabels: { content: 'แผนเนื้อหา', maps: 'แผนที่และรีวิว', influencers: 'งานกับครีเอเตอร์', partnerships: 'พันธมิตร', upsells: 'ยอดขายและยอดเฉลี่ย', automation: 'พนักงาน AI' },
    preferredFallbackReason: 'เปิดส่วนที่เลือกและทำงานต่อ', preferredContentCta: 'เปิดแผนเนื้อหา', preferredGeneralCta: 'ทำงานต่อ', urgentCta: 'ตรวจสอบงาน', preferredHint: 'พื้นที่ทำงานที่คุณเลือก', noTasksEyebrow: 'ไม่มีงานใหม่', emptyTitle: 'วันนี้คุณไม่ต้องทำอะไร', emptyNetworkReason: 'ไม่มีสาขาใดในเครือข่ายที่ต้องการการตัดสินใจของคุณตอนนี้', emptyReason: 'ไม่มีงานใหม่สำหรับคุณในข้อมูลล่าสุด', openPlatformQueue: 'เปิดคิวของแพลตฟอร์ม', openGrowthPlan: 'เปิดแผนการเติบโต',
  },
  ar: {
    preferredLabels: { content: 'خطة المحتوى', maps: 'الخرائط والتقييمات', influencers: 'العمل مع صناع المحتوى', partnerships: 'الشراكات', upsells: 'المبيعات ومتوسط الفاتورة', automation: 'موظفو الذكاء الاصطناعي' },
    preferredFallbackReason: 'افتح المجال المحدد وتابع العمل.', preferredContentCta: 'فتح خطة المحتوى', preferredGeneralCta: 'متابعة العمل', urgentCta: 'مراجعة المهمة', preferredHint: 'مجال عملك المحدد.', noTasksEyebrow: 'لا مهام جديدة', emptyTitle: 'لا شيء مطلوب منك اليوم', emptyNetworkReason: 'لا يحتاج أي موقع في الشبكة إلى قرارك حاليًا.', emptyReason: 'لا توجد مهام جديدة لك في آخر البيانات المحملة.', openPlatformQueue: 'فتح قائمة المنصة', openGrowthPlan: 'فتح خطة النمو',
  },
  ha: {
    preferredLabels: { content: 'Tsarin abun ciki', maps: 'Taswirori da ra’ayoyi', influencers: 'Aiki da masu ƙirƙira', partnerships: 'Haɗin gwiwa', upsells: 'Tallace-tallace da matsakaicin ciniki', automation: 'Ma’aikatan AI' },
    preferredFallbackReason: 'Buɗe sashen da aka zaɓa kuma ci gaba da aiki.', preferredContentCta: 'Buɗe tsarin abun ciki', preferredGeneralCta: 'Ci gaba da aiki', urgentCta: 'Duba aiki', preferredHint: 'Sashen aikin da ka zaɓa.', noTasksEyebrow: 'Babu sabbin ayyuka', emptyTitle: 'Babu abin da ake buƙata daga gare ka yau', emptyNetworkReason: 'Babu wani reshen hanyar sadarwa da ke buƙatar shawararka yanzu.', emptyReason: 'Babu sabbin ayyuka a gare ka a bayanan da aka loda na baya-bayan nan.', openPlatformQueue: 'Buɗe jerin dandali', openGrowthPlan: 'Buɗe tsarin bunƙasa',
  },
  tr: {
    preferredLabels: { content: 'İçerik planı', maps: 'Haritalar ve yorumlar', influencers: 'İçerik üreticileriyle çalışma', partnerships: 'İş ortaklıkları', upsells: 'Satışlar ve ortalama sepet', automation: 'Yapay zekâ çalışanları' },
    preferredFallbackReason: 'Seçilen alanı açın ve çalışmaya devam edin.', preferredContentCta: 'İçerik planını aç', preferredGeneralCta: 'Çalışmaya devam et', urgentCta: 'Görevi incele', preferredHint: 'Seçtiğiniz çalışma alanı.', noTasksEyebrow: 'Yeni görev yok', emptyTitle: 'Bugün sizden bir şey gerekmiyor', emptyNetworkReason: 'Ağdaki hiçbir konum şu anda kararınızı gerektirmiyor.', emptyReason: 'Son yüklenen verilerde sizin için yeni görev yok.', openPlatformQueue: 'Platform kuyruğunu aç', openGrowthPlan: 'Büyüme planını aç',
  },
  hy: {
    preferredLabels: { content: 'Բովանդակության պլան', maps: 'Քարտեզներ և կարծիքներ', influencers: 'Աշխատանք հեղինակների հետ', partnerships: 'Գործընկերություններ', upsells: 'Վաճառք և միջին չեկ', automation: 'AI աշխատակիցներ' },
    preferredFallbackReason: 'Բացեք ընտրված ուղղությունը և շարունակեք աշխատանքը։', preferredContentCta: 'Բացել բովանդակության պլանը', preferredGeneralCta: 'Շարունակել աշխատանքը', urgentCta: 'Ստուգել առաջադրանքը', preferredHint: 'Ձեր ընտրած աշխատանքային ուղղությունը։', noTasksEyebrow: 'Նոր առաջադրանքներ չկան', emptyTitle: 'Այսօր ձեզանից ոչինչ չի պահանջվում', emptyNetworkReason: 'Ցանցի որևէ կետ այժմ ձեր որոշումը չի պահանջում։', emptyReason: 'Վերջին բեռնված տվյալներում ձեզ համար նոր առաջադրանքներ չկան։', openPlatformQueue: 'Բացել հարթակի հերթը', openGrowthPlan: 'Բացել աճի պլանը',
  },
};

export const isTodayPreferredFlow = (value: string | undefined): value is TodayPreferredFlow => (
  value === 'content' || value === 'maps' || value === 'influencers' ||
  value === 'partnerships' || value === 'upsells' || value === 'automation'
);

export const getTodayMobileCopy = (language: Language) => copy[language];
