import type { Language } from '@/i18n/LanguageContext';
import type { AgentTemplate } from './types';

export type AgentTemplateGalleryCopy = {
  eyebrow: string;
  title: string;
  description: string;
  count: string;
  loading: string;
  scheduled: string;
  weekly: string;
  review: string;
  manual: string;
  certified: string;
  beta: string;
  testing: string;
  draft: string;
  needs: string;
  localos: string;
  preparing: string;
  use: string;
  plannedTitle: string;
  plannedDescription: string;
  recommended: string;
};

export const agentTemplateGalleryCopy: Record<Language, AgentTemplateGalleryCopy> = {
  ru: {
    eyebrow: 'Готовые задачи', title: 'Что поручить LocalOS',
    description: 'Выберите задачу — LocalOS создаст агента в режиме проверки. Запуски, публикации и отправки начнутся только после вашей проверки.',
    count: 'вариантов', loading: 'Загружаются готовые задачи', scheduled: 'Каждый день', weekly: 'Каждую неделю', review: 'При новом отзыве', manual: 'По команде',
    certified: 'Проверено', beta: 'Готово к проверке', testing: 'Идёт проверка', draft: 'В разработке',
    needs: 'Нужно подключить', localos: 'Только данные LocalOS', preparing: 'Создаём…', use: 'Создать для проверки',
    plannedTitle: 'В разработке', plannedDescription: 'Эти задачи пока нельзя включить.', recommended: 'Рекомендуем начать',
  },
  en: {
    eyebrow: 'Ready tasks', title: 'What should LocalOS handle?',
    description: 'Choose a task and LocalOS will create an agent in review mode. Runs, publishing, and messages start only after your review.',
    count: 'options', loading: 'Loading ready tasks', scheduled: 'Every day', weekly: 'Every week', review: 'When a new review arrives', manual: 'On demand',
    certified: 'Verified', beta: 'Ready to review', testing: 'Being tested', draft: 'In development',
    needs: 'Connect', localos: 'LocalOS data only', preparing: 'Creating…', use: 'Create for review',
    plannedTitle: 'In development', plannedDescription: 'These tasks cannot be enabled yet.', recommended: 'Recommended start',
  },
  fr: {
    eyebrow: 'Tâches prêtes', title: 'Que confier à LocalOS ?',
    description: 'Choisissez une tâche : LocalOS crée un agent en mode vérification. Les exécutions, publications et envois ne commencent qu’après votre contrôle.',
    count: 'options', loading: 'Chargement des tâches prêtes', scheduled: 'Chaque jour', weekly: 'Chaque semaine', review: 'À chaque nouvel avis', manual: 'À la demande',
    certified: 'Vérifié', beta: 'Prêt à vérifier', testing: 'En cours de test', draft: 'En développement',
    needs: 'À connecter', localos: 'Données LocalOS uniquement', preparing: 'Création…', use: 'Créer pour vérifier',
    plannedTitle: 'En développement', plannedDescription: 'Ces tâches ne peuvent pas encore être activées.', recommended: 'Point de départ conseillé',
  },
  es: {
    eyebrow: 'Tareas listas', title: '¿Qué debe hacer LocalOS?',
    description: 'Elige una tarea y LocalOS creará un agente en modo de revisión. Las ejecuciones, publicaciones y envíos solo empezarán después de tu revisión.',
    count: 'opciones', loading: 'Cargando tareas listas', scheduled: 'Cada día', weekly: 'Cada semana', review: 'Con una reseña nueva', manual: 'Bajo demanda',
    certified: 'Verificado', beta: 'Listo para revisar', testing: 'En pruebas', draft: 'En desarrollo',
    needs: 'Hay que conectar', localos: 'Solo datos de LocalOS', preparing: 'Creando…', use: 'Crear para revisar',
    plannedTitle: 'En desarrollo', plannedDescription: 'Estas tareas todavía no se pueden activar.', recommended: 'Recomendado para empezar',
  },
  el: {
    eyebrow: 'Έτοιμες εργασίες', title: 'Τι να αναλάβει το LocalOS;',
    description: 'Επιλέξτε εργασία και το LocalOS θα δημιουργήσει έναν πράκτορα σε λειτουργία ελέγχου. Εκτελέσεις, δημοσιεύσεις και αποστολές ξεκινούν μόνο μετά τον έλεγχό σας.',
    count: 'επιλογές', loading: 'Φόρτωση έτοιμων εργασιών', scheduled: 'Κάθε μέρα', weekly: 'Κάθε εβδομάδα', review: 'Με νέα κριτική', manual: 'Κατόπιν αιτήματος',
    certified: 'Επαληθευμένο', beta: 'Έτοιμο για έλεγχο', testing: 'Σε δοκιμή', draft: 'Σε ανάπτυξη',
    needs: 'Απαιτεί σύνδεση', localos: 'Μόνο δεδομένα LocalOS', preparing: 'Δημιουργία…', use: 'Δημιουργία για έλεγχο',
    plannedTitle: 'Σε ανάπτυξη', plannedDescription: 'Αυτές οι εργασίες δεν μπορούν ακόμη να ενεργοποιηθούν.', recommended: 'Προτεινόμενη αρχή',
  },
  de: {
    eyebrow: 'Fertige Aufgaben', title: 'Was soll LocalOS übernehmen?',
    description: 'Wählen Sie eine Aufgabe. LocalOS erstellt einen Agenten im Prüfmodus. Ausführungen, Veröffentlichungen und Nachrichten starten erst nach Ihrer Prüfung.',
    count: 'Optionen', loading: 'Fertige Aufgaben werden geladen', scheduled: 'Täglich', weekly: 'Wöchentlich', review: 'Bei einer neuen Bewertung', manual: 'Auf Abruf',
    certified: 'Geprüft', beta: 'Bereit zur Prüfung', testing: 'In Prüfung', draft: 'In Entwicklung',
    needs: 'Zu verbinden', localos: 'Nur LocalOS-Daten', preparing: 'Wird erstellt…', use: 'Zur Prüfung erstellen',
    plannedTitle: 'In Entwicklung', plannedDescription: 'Diese Aufgaben können noch nicht aktiviert werden.', recommended: 'Empfohlener Einstieg',
  },
  th: {
    eyebrow: 'งานพร้อมใช้', title: 'ต้องการให้ LocalOS ทำอะไร',
    description: 'เลือกงาน แล้ว LocalOS จะสร้างเอเจนต์ในโหมดตรวจสอบ การทำงาน การเผยแพร่ และการส่งข้อความจะเริ่มหลังจากคุณตรวจสอบแล้วเท่านั้น',
    count: 'ตัวเลือก', loading: 'กำลังโหลดงานพร้อมใช้', scheduled: 'ทุกวัน', weekly: 'ทุกสัปดาห์', review: 'เมื่อมีรีวิวใหม่', manual: 'เมื่อต้องการ',
    certified: 'ตรวจสอบแล้ว', beta: 'พร้อมให้ตรวจสอบ', testing: 'กำลังทดสอบ', draft: 'กำลังพัฒนา',
    needs: 'ต้องเชื่อมต่อ', localos: 'ใช้เฉพาะข้อมูล LocalOS', preparing: 'กำลังสร้าง…', use: 'สร้างเพื่อตรวจสอบ',
    plannedTitle: 'กำลังพัฒนา', plannedDescription: 'งานเหล่านี้ยังเปิดใช้งานไม่ได้', recommended: 'แนะนำให้เริ่มจากงานนี้',
  },
  ar: {
    eyebrow: 'مهام جاهزة', title: 'ما الذي تريد أن يتولاه LocalOS؟',
    description: 'اختر مهمة وسيُنشئ LocalOS وكيلاً في وضع المراجعة. لن تبدأ عمليات التشغيل أو النشر أو الإرسال إلا بعد مراجعتك.',
    count: 'خيارات', loading: 'جارٍ تحميل المهام الجاهزة', scheduled: 'يوميًا', weekly: 'أسبوعيًا', review: 'عند وصول مراجعة جديدة', manual: 'عند الطلب',
    certified: 'تم التحقق', beta: 'جاهز للمراجعة', testing: 'قيد الاختبار', draft: 'قيد التطوير',
    needs: 'يتطلب ربط', localos: 'بيانات LocalOS فقط', preparing: 'جارٍ الإنشاء…', use: 'إنشاء للمراجعة',
    plannedTitle: 'قيد التطوير', plannedDescription: 'لا يمكن تفعيل هذه المهام بعد.', recommended: 'بداية موصى بها',
  },
  ha: {
    eyebrow: 'Ayyuka da aka shirya', title: 'Me LocalOS zai ɗauka?',
    description: 'Zaɓi aiki, LocalOS zai ƙirƙiri wakili a yanayin dubawa. Gudanarwa, wallafawa da aikawa za su fara ne bayan ka duba.',
    count: 'zaɓuɓɓuka', loading: 'Ana loda ayyukan da aka shirya', scheduled: 'Kowace rana', weekly: 'Kowane mako', review: 'Idan sabon review ya zo', manual: 'Bisa buƙata',
    certified: 'An tabbatar', beta: 'A shirye don dubawa', testing: 'Ana gwadawa', draft: 'Ana ginawa',
    needs: 'A haɗa', localos: 'Bayanan LocalOS kawai', preparing: 'Ana ƙirƙirawa…', use: 'Ƙirƙira don dubawa',
    plannedTitle: 'Ana ginawa', plannedDescription: 'Ba za a iya kunna waɗannan ayyukan yanzu ba.', recommended: 'An ba da shawarar farawa',
  },
  tr: {
    eyebrow: 'Hazır görevler', title: 'LocalOS neyi üstlensin?',
    description: 'Bir görev seçin; LocalOS inceleme modunda bir ajan oluştursun. Çalıştırma, yayınlama ve gönderme yalnızca sizin kontrolünüzden sonra başlar.',
    count: 'seçenek', loading: 'Hazır görevler yükleniyor', scheduled: 'Her gün', weekly: 'Her hafta', review: 'Yeni yorum geldiğinde', manual: 'İstek üzerine',
    certified: 'Doğrulandı', beta: 'İncelemeye hazır', testing: 'Test ediliyor', draft: 'Geliştiriliyor',
    needs: 'Bağlantı gerekli', localos: 'Yalnızca LocalOS verileri', preparing: 'Oluşturuluyor…', use: 'İnceleme için oluştur',
    plannedTitle: 'Geliştiriliyor', plannedDescription: 'Bu görevler henüz etkinleştirilemez.', recommended: 'Önerilen başlangıç',
  },
};

export const getAgentTemplateGalleryCopy = (language: Language) => agentTemplateGalleryCopy[language];

export const getLocalizedAgentTemplateContent = (template: AgentTemplate, language: Language) => {
  if (language === 'ru') {
    return { name: template.name, business_result: template.business_result };
  }
  return template.localized_content?.[language]
    || template.localized_content?.en
    || { name: template.name, business_result: template.business_result };
};
