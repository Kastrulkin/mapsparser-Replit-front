import type { Language } from '@/i18n/LanguageContext';

type AttentionCopy = { title: string; description: string };

export type OperatorPageCopy = {
  title: string;
  description: string;
  priorityTitle: string;
  priorityDescription: string;
  taskFallback: string;
  betaTitle: string;
  betaDescription: string;
  selectedBusiness: string;
  safetyNote: string;
  loadingHistory: string;
  emptyTitle: string;
  emptyDescription: string;
  examples: string[];
  placeholder: string;
  send: string;
  sendHint: string;
  newlineHint: string;
  attention: Record<string, AttentionCopy>;
  metrics: Record<string, string>;
  sources: Record<string, string>;
  mismatchTemplate: string;
  location: { loading: string; select: string; fallback: string };
  feedback: {
    button: string;
    title: string;
    description: string;
    emptyTitle: string;
    emptyDescription: string;
    successTitle: string;
    successDescription: string;
    errorTitle: string;
    errorDescription: string;
    section: string;
    placeholder: string;
    cancel: string;
    send: string;
  };
};

const sharedAttention = (
  pendingApprovals: AttentionCopy,
  reviewDrafts: AttentionCopy,
  pendingNews: AttentionCopy,
  partnerships: AttentionCopy,
  staleMaps: AttentionCopy,
  noUrgent: AttentionCopy,
): Record<string, AttentionCopy> => ({
  pending_approvals: pendingApprovals,
  review_reply_drafts: reviewDrafts,
  pending_news: pendingNews,
  partnership_leads_ready: partnerships,
  map_data_stale: staleMaps,
  no_urgent_items: noUrgent,
});

const ru: OperatorPageCopy = {
  title: 'Оператор', description: 'Напишите задачу обычным языком. Оператор выполнит её, уточнит недостающее или безопасно передаст в нужный раздел.', priorityTitle: 'Что важно сейчас', priorityDescription: 'Это же саммари показывает Telegram для выбранного бизнеса.', taskFallback: 'Задача', betaTitle: 'Функция в стадии beta-тестирования', betaDescription: 'Если в Операторе что-то сработало не так, выглядит странно или не доводит задачу до результата, сообщите о проблеме.', selectedBusiness: 'Выбранный бизнес', safetyNote: 'Команды выполняются внутри LocalOS. Публикация во внешние карты остаётся ручной.', loadingHistory: 'Загружаем историю…', emptyTitle: 'Напишите команду', emptyDescription: 'Можно изменить услугу, создать контент, проверить данные или попросить открыть нужный результат.', examples: ['Что ты умеешь?', 'Измени цену услуги Маникюр на 1500', 'Создай новость про летнюю акцию', 'Сделай контент-план на 30 дней', 'Покажи отзывы без ответа'], placeholder: 'Напишите задачу: измени цену услуги, создай новость, сделай контент-план…', send: 'Отправить', sendHint: 'отправить', newlineHint: 'новая строка',
  attention: sharedAttention(
    { title: 'Действия ждут подтверждения', description: 'Есть операции, которые нельзя выполнить без ручного решения владельца.' },
    { title: 'Черновики ответов готовы', description: 'LocalOS может подготовить тексты, но публикация в карты остаётся ручной через копирование.' },
    { title: 'Черновики новостей ждут решения', description: 'Проверьте сохранённые материалы перед публикацией или дальнейшей работой.' },
    { title: 'Партнёрства готовы к разбору', description: 'В списке есть партнёры, с которыми можно перейти к выбору канала или черновику сообщения.' },
    { title: 'Данные карт стоит обновить', description: 'Сейчас показаны последние известные данные. Обновление карт относится к платным внешним действиям.' },
    { title: 'Срочных задач не найдено', description: 'По сохранённым данным нет отзывов без ответа, ожидающих подтверждений или черновиков на разбор.' },
  ),
  metrics: { provider_rating: 'Рейтинг на карте', provider_reviews_total: 'Отзывов на карте', imported_reviews_total: 'Загружено в LocalOS', imported_reviews_unanswered: 'Без ответа в LocalOS' },
  sources: { cards: 'Карты', reviews: 'Отзывы LocalOS' },
  mismatchTemplate: 'На карте указано {provider} отзывов, в LocalOS загружено {imported}. Это разные показатели; для полного списка нужно обновить данные.',
  location: { loading: 'Загрузка…', select: 'Выберите точку', fallback: 'Точка' },
  feedback: { button: 'Сообщить о проблеме', title: 'Сообщить о проблеме', description: 'Опишите, что вы увидели в разделе. Мы сохраним сообщение вместе с контекстом страницы и бизнеса.', emptyTitle: 'Опишите проблему', emptyDescription: 'Добавьте пару слов: что именно сломалось или выглядит неправильно.', successTitle: 'Сообщение отправлено', successDescription: 'Спасибо. Мы сохранили проблему и вернёмся к ней в beta-разборе.', errorTitle: 'Не удалось отправить сообщение', errorDescription: 'Попробуйте ещё раз через минуту.', section: 'Раздел', placeholder: 'Например: после запуска теста не видно результат, кнопка не срабатывает, таблица выглядит сломанной…', cancel: 'Отмена', send: 'Отправить' },
};

const en: OperatorPageCopy = {
  title: 'Operator', description: 'Describe a task in plain language. Operator will complete it, ask for missing details, or safely take you to the right section.', priorityTitle: 'What matters now', priorityDescription: 'Telegram shows the same summary for the selected business.', taskFallback: 'Task', betaTitle: 'Feature in beta testing', betaDescription: 'If Operator behaves unexpectedly or does not complete a task, please report the problem.', selectedBusiness: 'Selected business', safetyNote: 'Commands run inside LocalOS. Publishing to external map platforms remains manual.', loadingHistory: 'Loading history…', emptyTitle: 'Enter a command', emptyDescription: 'Update a service, create content, check data, or ask Operator to open the right result.', examples: ['What can you do?', 'Change the Manicure price to 1500', 'Create news about a summer offer', 'Make a 30-day content plan', 'Show unanswered reviews'], placeholder: 'Enter a task: change a service price, create news, make a content plan…', send: 'Send', sendHint: 'send', newlineHint: 'new line',
  attention: sharedAttention(
    { title: 'Actions need approval', description: 'Some operations require a manual decision from the owner.' },
    { title: 'Reply drafts are ready', description: 'LocalOS can prepare text, but publishing to map platforms remains manual.' },
    { title: 'News drafts need a decision', description: 'Review saved materials before publishing or continuing the work.' },
    { title: 'Partnerships are ready for review', description: 'The shortlist contains partners ready for channel selection or a message draft.' },
    { title: 'Map data should be updated', description: 'The latest known data is shown. Refreshing map data is a paid external action.' },
    { title: 'No urgent tasks found', description: 'Saved data contains no unanswered reviews, pending approvals, or drafts needing review.' },
  ),
  metrics: { provider_rating: 'Map rating', provider_reviews_total: 'Reviews on maps', imported_reviews_total: 'Loaded into LocalOS', imported_reviews_unanswered: 'Unanswered in LocalOS' },
  sources: { cards: 'Maps', reviews: 'LocalOS reviews' },
  mismatchTemplate: 'Maps show {provider} reviews, while {imported} are loaded into LocalOS. These are different metrics; refresh the data to load the full list.',
  location: { loading: 'Loading…', select: 'Select a location', fallback: 'Location' },
  feedback: { button: 'Report a problem', title: 'Report a problem', description: 'Describe what you saw in this section. We will save the report with the page and business context.', emptyTitle: 'Describe the problem', emptyDescription: 'Add a few words about what broke or looks wrong.', successTitle: 'Message sent', successDescription: 'Thank you. We saved the problem for beta review.', errorTitle: 'Could not send the message', errorDescription: 'Please try again in a minute.', section: 'Section', placeholder: 'For example: the result is missing, a button does not work, or the table looks broken…', cancel: 'Cancel', send: 'Send' },
};

const tr: OperatorPageCopy = {
  title: 'Operatör', description: 'Görevinizi günlük dille yazın. Operatör görevi tamamlar, eksik bilgiyi sorar veya sizi güvenle doğru bölüme yönlendirir.', priorityTitle: 'Şu anda önemli olanlar', priorityDescription: 'Telegram, seçili işletme için aynı özeti gösterir.', taskFallback: 'Görev', betaTitle: 'Özellik beta testinde', betaDescription: 'Operatör beklenmedik çalışır veya görevi tamamlamazsa lütfen sorunu bildirin.', selectedBusiness: 'Seçili işletme', safetyNote: 'Komutlar LocalOS içinde yürütülür. Harita platformlarında yayınlama manuel kalır.', loadingHistory: 'Geçmiş yükleniyor…', emptyTitle: 'Bir komut yazın', emptyDescription: 'Bir hizmeti değiştirin, içerik oluşturun, verileri kontrol edin veya doğru sonucu açmasını isteyin.', examples: ['Neler yapabilirsin?', 'Manikür fiyatını 1500 olarak değiştir', 'Yaz kampanyası hakkında haber oluştur', '30 günlük içerik planı hazırla', 'Yanıtsız yorumları göster'], placeholder: 'Görev yazın: hizmet fiyatını değiştir, haber oluştur, içerik planı hazırla…', send: 'Gönder', sendHint: 'gönder', newlineHint: 'yeni satır',
  attention: sharedAttention(
    { title: 'İşlemler onay bekliyor', description: 'Bazı işlemler işletme sahibinin manuel kararını gerektirir.' },
    { title: 'Yanıt taslakları hazır', description: 'LocalOS metinleri hazırlar; harita platformlarında yayınlama manuel kalır.' },
    { title: 'Haber taslakları karar bekliyor', description: 'Yayınlamadan veya çalışmaya devam etmeden önce kayıtlı materyalleri kontrol edin.' },
    { title: 'İş ortaklıkları incelemeye hazır', description: 'Kısa listede kanal seçimine veya mesaj taslağına geçilebilecek ortaklar var.' },
    { title: 'Harita verileri güncellenmeli', description: 'Şu anda bilinen son veriler gösteriliyor. Harita yenileme ücretli bir dış işlemdir.' },
    { title: 'Acil görev bulunamadı', description: 'Kayıtlı verilerde yanıtsız yorum, bekleyen onay veya incelenecek taslak yok.' },
  ),
  metrics: { provider_rating: 'Harita puanı', provider_reviews_total: 'Haritalardaki yorumlar', imported_reviews_total: 'LocalOS’a yüklenen', imported_reviews_unanswered: 'LocalOS’ta yanıtsız' },
  sources: { cards: 'Haritalar', reviews: 'LocalOS yorumları' },
  mismatchTemplate: 'Haritalarda {provider} yorum görünüyor, LocalOS’a {imported} yorum yüklenmiş. Bunlar farklı ölçümlerdir; tam liste için verileri güncelleyin.',
  location: { loading: 'Yükleniyor…', select: 'Konum seçin', fallback: 'Konum' },
  feedback: { button: 'Sorun bildir', title: 'Sorun bildir', description: 'Bu bölümde ne gördüğünüzü açıklayın. Mesajı sayfa ve işletme bağlamıyla kaydedeceğiz.', emptyTitle: 'Sorunu açıklayın', emptyDescription: 'Neyin bozulduğunu veya yanlış göründüğünü birkaç kelimeyle yazın.', successTitle: 'Mesaj gönderildi', successDescription: 'Teşekkürler. Sorunu beta incelemesi için kaydettik.', errorTitle: 'Mesaj gönderilemedi', errorDescription: 'Bir dakika sonra tekrar deneyin.', section: 'Bölüm', placeholder: 'Örneğin: sonuç görünmüyor, düğme çalışmıyor veya tablo bozuk görünüyor…', cancel: 'İptal', send: 'Gönder' },
};

const adapt = (base: OperatorPageCopy, values: Partial<OperatorPageCopy>): OperatorPageCopy => ({ ...base, ...values });

const fr = adapt(en, { title: 'Opérateur', description: 'Décrivez une tâche en langage courant. L’Opérateur l’exécute, demande les précisions manquantes ou vous dirige vers la bonne section.', priorityTitle: 'Ce qui compte maintenant', priorityDescription: 'Telegram affiche le même résumé pour l’entreprise sélectionnée.', taskFallback: 'Tâche', betaTitle: 'Fonction en test bêta', betaDescription: 'Si l’Opérateur se comporte de façon inattendue ou ne termine pas une tâche, signalez le problème.', selectedBusiness: 'Entreprise sélectionnée', safetyNote: 'Les commandes s’exécutent dans LocalOS. La publication sur les cartes reste manuelle.', loadingHistory: 'Chargement de l’historique…', emptyTitle: 'Saisissez une commande', emptyDescription: 'Modifiez un service, créez du contenu, vérifiez les données ou demandez d’ouvrir le bon résultat.', examples: ['Que pouvez-vous faire ?', 'Changez le prix de la manucure à 1500', 'Créez une actualité sur l’offre d’été', 'Préparez un plan de contenu de 30 jours', 'Montrez les avis sans réponse'], placeholder: 'Saisissez une tâche : modifier un prix, créer une actualité, préparer un plan…', send: 'Envoyer', sendHint: 'envoyer', newlineHint: 'nouvelle ligne', location: { loading: 'Chargement…', select: 'Choisir un établissement', fallback: 'Établissement' } });
const es = adapt(en, { title: 'Operador', description: 'Describe una tarea con lenguaje normal. El Operador la realizará, pedirá lo que falte o te llevará de forma segura a la sección correcta.', priorityTitle: 'Lo importante ahora', priorityDescription: 'Telegram muestra el mismo resumen para el negocio seleccionado.', taskFallback: 'Tarea', betaTitle: 'Función en pruebas beta', betaDescription: 'Si el Operador funciona de forma inesperada o no completa una tarea, informa del problema.', selectedBusiness: 'Negocio seleccionado', safetyNote: 'Los comandos se ejecutan dentro de LocalOS. La publicación en mapas sigue siendo manual.', loadingHistory: 'Cargando historial…', emptyTitle: 'Escribe un comando', emptyDescription: 'Cambia un servicio, crea contenido, comprueba datos o pide abrir el resultado correcto.', examples: ['¿Qué puedes hacer?', 'Cambia el precio de Manicura a 1500', 'Crea una noticia sobre la oferta de verano', 'Prepara un plan de contenido de 30 días', 'Muestra reseñas sin respuesta'], placeholder: 'Escribe una tarea: cambia un precio, crea noticias, prepara un plan…', send: 'Enviar', sendHint: 'enviar', newlineHint: 'nueva línea', location: { loading: 'Cargando…', select: 'Selecciona una ubicación', fallback: 'Ubicación' } });
const de = adapt(en, { title: 'Operator', description: 'Beschreiben Sie eine Aufgabe in Alltagssprache. Der Operator führt sie aus, fragt fehlende Angaben ab oder öffnet sicher den passenden Bereich.', priorityTitle: 'Jetzt wichtig', priorityDescription: 'Telegram zeigt dieselbe Zusammenfassung für das gewählte Unternehmen.', taskFallback: 'Aufgabe', betaTitle: 'Funktion im Beta-Test', betaDescription: 'Wenn der Operator unerwartet arbeitet oder eine Aufgabe nicht beendet, melden Sie das Problem.', selectedBusiness: 'Ausgewähltes Unternehmen', safetyNote: 'Befehle laufen innerhalb von LocalOS. Die Veröffentlichung auf Karten bleibt manuell.', loadingHistory: 'Verlauf wird geladen…', emptyTitle: 'Befehl eingeben', emptyDescription: 'Ändern Sie eine Leistung, erstellen Sie Inhalte, prüfen Sie Daten oder öffnen Sie das richtige Ergebnis.', examples: ['Was können Sie tun?', 'Ändern Sie den Manikürepreis auf 1500', 'Erstellen Sie eine Nachricht zum Sommerangebot', 'Erstellen Sie einen 30-Tage-Inhaltsplan', 'Zeigen Sie unbeantwortete Bewertungen'], placeholder: 'Aufgabe eingeben: Preis ändern, Nachricht erstellen, Inhaltsplan vorbereiten…', send: 'Senden', sendHint: 'senden', newlineHint: 'neue Zeile', location: { loading: 'Wird geladen…', select: 'Standort wählen', fallback: 'Standort' } });
const el = adapt(en, { title: 'Χειριστής', description: 'Περιγράψτε μια εργασία με απλή γλώσσα. Ο Χειριστής θα την εκτελέσει, θα ζητήσει ό,τι λείπει ή θα ανοίξει με ασφάλεια τη σωστή ενότητα.', priorityTitle: 'Τι έχει σημασία τώρα', priorityDescription: 'Το Telegram δείχνει την ίδια σύνοψη για την επιλεγμένη επιχείρηση.', taskFallback: 'Εργασία', betaTitle: 'Λειτουργία σε δοκιμή beta', betaDescription: 'Αν ο Χειριστής λειτουργήσει απρόσμενα ή δεν ολοκληρώσει μια εργασία, αναφέρετε το πρόβλημα.', selectedBusiness: 'Επιλεγμένη επιχείρηση', safetyNote: 'Οι εντολές εκτελούνται μέσα στο LocalOS. Η δημοσίευση στους χάρτες παραμένει χειροκίνητη.', loadingHistory: 'Φόρτωση ιστορικού…', emptyTitle: 'Γράψτε μια εντολή', emptyDescription: 'Αλλάξτε μια υπηρεσία, δημιουργήστε περιεχόμενο, ελέγξτε δεδομένα ή ζητήστε το σωστό αποτέλεσμα.', examples: ['Τι μπορείτε να κάνετε;', 'Αλλάξτε την τιμή μανικιούρ σε 1500', 'Δημιουργήστε νέο για καλοκαιρινή προσφορά', 'Ετοιμάστε πλάνο περιεχομένου 30 ημερών', 'Δείξτε κριτικές χωρίς απάντηση'], placeholder: 'Γράψτε εργασία: αλλάξτε τιμή, δημιουργήστε νέο, ετοιμάστε πλάνο…', send: 'Αποστολή', sendHint: 'αποστολή', newlineHint: 'νέα γραμμή', location: { loading: 'Φόρτωση…', select: 'Επιλέξτε τοποθεσία', fallback: 'Τοποθεσία' } });
const th = adapt(en, { title: 'โอเปอเรเตอร์', description: 'อธิบายงานด้วยภาษาธรรมดา โอเปอเรเตอร์จะทำงาน ขอข้อมูลที่ขาด หรือพาไปยังส่วนที่ถูกต้องอย่างปลอดภัย', priorityTitle: 'สิ่งสำคัญตอนนี้', priorityDescription: 'Telegram แสดงสรุปเดียวกันสำหรับธุรกิจที่เลือก', taskFallback: 'งาน', betaTitle: 'ฟีเจอร์อยู่ระหว่างทดสอบเบต้า', betaDescription: 'หากโอเปอเรเตอร์ทำงานผิดปกติหรือทำงานไม่เสร็จ โปรดรายงานปัญหา', selectedBusiness: 'ธุรกิจที่เลือก', safetyNote: 'คำสั่งทำงานภายใน LocalOS การเผยแพร่ไปยังแผนที่ยังเป็นแบบทำด้วยตนเอง', loadingHistory: 'กำลังโหลดประวัติ…', emptyTitle: 'พิมพ์คำสั่ง', emptyDescription: 'แก้ไขบริการ สร้างเนื้อหา ตรวจสอบข้อมูล หรือขอให้เปิดผลลัพธ์ที่ถูกต้อง', examples: ['คุณทำอะไรได้บ้าง?', 'เปลี่ยนราคาทำเล็บเป็น 1500', 'สร้างข่าวเกี่ยวกับโปรโมชันฤดูร้อน', 'ทำแผนเนื้อหา 30 วัน', 'แสดงรีวิวที่ยังไม่ได้ตอบ'], placeholder: 'พิมพ์งาน: เปลี่ยนราคา สร้างข่าว ทำแผนเนื้อหา…', send: 'ส่ง', sendHint: 'ส่ง', newlineHint: 'บรรทัดใหม่', location: { loading: 'กำลังโหลด…', select: 'เลือกสถานที่', fallback: 'สถานที่' } });
const ar = adapt(en, { title: 'المشغّل', description: 'اكتب المهمة بلغة بسيطة. ينفذها المشغّل أو يطلب المعلومات الناقصة أو ينقلك بأمان إلى القسم المناسب.', priorityTitle: 'ما يهم الآن', priorityDescription: 'يعرض Telegram الملخص نفسه للنشاط المحدد.', taskFallback: 'مهمة', betaTitle: 'الميزة قيد الاختبار التجريبي', betaDescription: 'إذا عمل المشغّل بشكل غير متوقع أو لم يكمل المهمة، فأبلغ عن المشكلة.', selectedBusiness: 'النشاط المحدد', safetyNote: 'تُنفذ الأوامر داخل LocalOS. يظل النشر على الخرائط يدويًا.', loadingHistory: 'جارٍ تحميل السجل…', emptyTitle: 'اكتب أمرًا', emptyDescription: 'عدّل خدمة أو أنشئ محتوى أو تحقق من البيانات أو اطلب فتح النتيجة المناسبة.', examples: ['ماذا يمكنك أن تفعل؟', 'غيّر سعر المانيكير إلى 1500', 'أنشئ خبرًا عن العرض الصيفي', 'أعد خطة محتوى لمدة 30 يومًا', 'اعرض المراجعات بلا رد'], placeholder: 'اكتب مهمة: غيّر سعرًا، أنشئ خبرًا، أعد خطة محتوى…', send: 'إرسال', sendHint: 'إرسال', newlineHint: 'سطر جديد', location: { loading: 'جارٍ التحميل…', select: 'اختر موقعًا', fallback: 'موقع' } });
const ha = adapt(en, { title: 'Operator', description: 'Rubuta aiki da yare mai sauƙi. Operator zai yi shi, ya nemi bayanin da ya rage ko ya buɗe sashen da ya dace.', priorityTitle: 'Abin da ya fi muhimmanci yanzu', priorityDescription: 'Telegram yana nuna wannan taƙaitaccen bayani ga kasuwancin da aka zaɓa.', taskFallback: 'Aiki', betaTitle: 'Ana gwada wannan fasali', betaDescription: 'Idan Operator ya yi aiki ba yadda ake tsammani ba ko bai gama aiki ba, ka ba da rahoton matsalar.', selectedBusiness: 'Kasuwancin da aka zaɓa', safetyNote: 'Ana aiwatar da umarni a cikin LocalOS. Wallafawa zuwa taswira yana nan da hannu.', loadingHistory: 'Ana loda tarihi…', emptyTitle: 'Rubuta umarni', emptyDescription: 'Canja service, ƙirƙiri abun ciki, duba bayanai ko nemi a buɗe sakamakon da ya dace.', examples: ['Me za ka iya yi?', 'Canja farashin manicure zuwa 1500', 'Ƙirƙiri labarin tayin bazara', 'Shirya tsarin abun ciki na kwana 30', 'Nuna reviews marasa amsa'], placeholder: 'Rubuta aiki: canja farashi, ƙirƙiri labari, shirya tsari…', send: 'Aika', sendHint: 'aika', newlineHint: 'sabon layi', location: { loading: 'Ana lodawa…', select: 'Zaɓi wuri', fallback: 'Wuri' } });

const copyByLanguage: Record<Language, OperatorPageCopy> = { ru, en, fr, es, el, de, th, ar, ha, tr };

export const operatorPageCopyForLanguage = (language: Language) => copyByLanguage[language];

export const fillOperatorTemplate = (template: string, values: Record<string, string | number>) => (
  Object.entries(values).reduce((result, [key, value]) => result.replace(`{${key}}`, String(value)), template)
);

export const localizeDemoBusinessName = (name: string, language: Language) => {
  const normalized = String(name || '').trim();
  if (language !== 'ru' && normalized.toLowerCase() === 'рога и копыта') return 'Roga i Kopyta';
  return normalized;
};

export const localizedAttentionCopy = (copy: OperatorPageCopy, id?: string, title?: string, description?: string) => {
  const localized = id ? copy.attention[id] : undefined;
  return { title: localized?.title || title || copy.taskFallback, description: localized?.description || description || '' };
};

export const localizedMetricLabel = (copy: OperatorPageCopy, key?: string, fallback?: string) => (
  (key && copy.metrics[key]) || fallback || 'LocalOS'
);

export const localizedMetricSource = (copy: OperatorPageCopy, source?: string, sourceLabel?: string) => {
  const normalized = `${sourceLabel || ''} ${source || ''}`.toLowerCase();
  if (normalized.includes('карт') || normalized.includes('card')) return copy.sources.cards;
  if (normalized.includes('отзыв') || normalized.includes('review')) return copy.sources.reviews;
  return sourceLabel || source || 'LocalOS';
};

export const localizedDataWarning = (copy: OperatorPageCopy, warning: string) => {
  const values = String(warning || '').match(/\d+/g) || [];
  if (values.length < 2) return warning;
  return fillOperatorTemplate(copy.mismatchTemplate, { provider: values[0], imported: values[1] });
};
