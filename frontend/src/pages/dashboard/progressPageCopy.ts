import type { Language } from '@/i18n/LanguageContext';

export type ProgressPageCopy = {
  eyebrow: string;
  title: string;
  description: string;
  selectBusinessDescription: string;
  loadingDescription: string;
  fallbackDescription: string;
  refresh: string;
  retry: string;
  loadErrorTitle: string;
  loadErrorDescription: string;
  staleData: string;
  newResult: string;
  confirmedPath: string;
  confirmedSteps: string;
  resultsIn30Days: string;
  activeAreas: string;
  needAttention: string;
  currentPriority: string;
  continueWorking: string;
  result: string;
  growthAreas: string;
  growthAreasDescription: string;
  completed: string;
  of: string;
  path: string;
  nextStepOutcome: string;
  currentAudit: string;
  auditReady: string;
  auditReadyUpdated: string;
  auditReadySuffix: string;
  auditPending: string;
  viewFullAudit: string;
  mapsAndReputation: string;
  fullAudit: string;
  location: string;
  auditDescription: string;
  selectAuditLocation: string;
  selectLocation: string;
  hideFullAudit: string;
  parseQueued: string;
  parseProcessing: string;
  cardHistory: string;
  recentResults: string;
  recentResultsEmpty: string;
};

const ru: ProgressPageCopy = {
  eyebrow: 'Картина бизнеса', title: 'Прогресс бизнеса', description: 'Что уже сделано, где нужна помощь и какой шаг даст следующий практический результат.', selectBusinessDescription: 'Выберите бизнес, чтобы увидеть сделанное и следующий шаг.', loadingDescription: 'Собираем подтверждённые результаты из рабочих разделов LocalOS.', fallbackDescription: 'Общая картина выполненной работы и следующих действий.', refresh: 'Обновить', retry: 'Повторить', loadErrorTitle: 'Не удалось собрать общую картину', loadErrorDescription: 'Попробуйте обновить данные.', staleData: 'Новая сводка пока не загрузилась. Показываем предыдущие подтверждённые данные.', newResult: 'Новый результат', confirmedPath: 'Подтверждённый путь', confirmedSteps: 'шагов подтверждены реальными данными', resultsIn30Days: 'результатов за 30 дней', activeAreas: 'направлений начаты', needAttention: 'требуют внимания', currentPriority: 'Сейчас важнее всего', continueWorking: 'Продолжайте работу', result: 'Результат', growthAreas: 'Направления роста', growthAreasDescription: 'Откройте направление, чтобы увидеть сделанное и следующий шаг.', completed: 'Сделано', of: 'из', path: 'Путь', nextStepOutcome: 'Что даст следующий шаг', currentAudit: 'Текущий аудит', auditReady: 'Аудит готов', auditReadyUpdated: 'и обновлён', auditReadySuffix: 'Откройте его, чтобы увидеть факты и приоритеты карточки.', auditPending: 'Полный аудит появится здесь после первого успешного сбора данных.', viewFullAudit: 'Посмотреть полный аудит', mapsAndReputation: 'Карты и репутация', fullAudit: 'Полный аудит карточки', location: 'Точка', auditDescription: 'Данные, причины проблем и конкретные действия.', selectAuditLocation: 'Выбрать точку для аудита', selectLocation: 'Выберите точку', hideFullAudit: 'Скрыть полный аудит', parseQueued: 'Сбор данных ждёт запуска. Текущий аудит остаётся доступен.', parseProcessing: 'Собираем свежие данные. Текущий аудит остаётся на экране.', cardHistory: 'История обновлений карточки', recentResults: 'Недавние результаты', recentResultsEmpty: 'Здесь появятся подтверждённые результаты: готовый аудит, контент-план, найденные партнёры, выполненные задачи и внедрённые допродажи.',
};

const tr: ProgressPageCopy = {
  eyebrow: 'İşletmenin genel görünümü', title: 'İşletme ilerlemesi', description: 'Nelerin tamamlandığını, nerede desteğe ihtiyaç olduğunu ve hangi adımın bir sonraki somut sonucu getireceğini görün.', selectBusinessDescription: 'Tamamlanan işleri ve sonraki adımı görmek için bir işletme seçin.', loadingDescription: 'LocalOS çalışma alanlarındaki doğrulanmış sonuçlar toplanıyor.', fallbackDescription: 'Tamamlanan çalışmaların ve sonraki adımların genel görünümü.', refresh: 'Yenile', retry: 'Tekrar dene', loadErrorTitle: 'Genel görünüm oluşturulamadı', loadErrorDescription: 'Verileri yenilemeyi deneyin.', staleData: 'Yeni özet henüz yüklenmedi. Önceki doğrulanmış veriler gösteriliyor.', newResult: 'Yeni sonuç', confirmedPath: 'Doğrulanmış ilerleme', confirmedSteps: 'adım gerçek verilerle doğrulandı', resultsIn30Days: 'son 30 gündeki sonuç', activeAreas: 'başlatılan alan', needAttention: 'dikkat gerektiriyor', currentPriority: 'Şu anda en önemli', continueWorking: 'Çalışmaya devam edin', result: 'Sonuç', growthAreas: 'Büyüme alanları', growthAreasDescription: 'Tamamlananları ve sonraki adımı görmek için bir alanı açın.', completed: 'Tamamlandı', of: '/', path: 'İlerleme', nextStepOutcome: 'Sonraki adımın sağlayacağı sonuç', currentAudit: 'Mevcut denetim', auditReady: 'Denetim hazır', auditReadyUpdated: 'son güncelleme', auditReadySuffix: 'Kart bilgilerini ve öncelikleri görmek için açın.', auditPending: 'İlk başarılı veri toplama işleminden sonra tam denetim burada görünecek.', viewFullAudit: 'Tam denetimi görüntüle', mapsAndReputation: 'Haritalar ve itibar', fullAudit: 'İşletme kartının tam denetimi', location: 'Konum', auditDescription: 'Veriler, sorunların nedenleri ve somut adımlar.', selectAuditLocation: 'Denetim için konum seçin', selectLocation: 'Konum seçin', hideFullAudit: 'Tam denetimi gizle', parseQueued: 'Veri toplama başlatılmayı bekliyor. Mevcut denetim kullanılabilir.', parseProcessing: 'Güncel veriler toplanıyor. Mevcut denetim ekranda kalacak.', cardHistory: 'İşletme kartı güncelleme geçmişi', recentResults: 'Son sonuçlar', recentResultsEmpty: 'Doğrulanmış sonuçlar burada görünecek: tamamlanan denetim, içerik planı, bulunan iş ortakları, bitirilen görevler ve uygulanan ek satışlar.',
};

const el: ProgressPageCopy = {
  eyebrow: 'Επισκόπηση επιχείρησης', title: 'Πρόοδος επιχείρησης', description: 'Δείτε τι έχει ολοκληρωθεί, πού χρειάζεται βοήθεια και ποιο βήμα θα φέρει το επόμενο πρακτικό αποτέλεσμα.', selectBusinessDescription: 'Επιλέξτε επιχείρηση για να δείτε την πρόοδο και το επόμενο βήμα.', loadingDescription: 'Συλλέγουμε επιβεβαιωμένα αποτελέσματα από τις ενότητες του LocalOS.', fallbackDescription: 'Συνολική εικόνα ολοκληρωμένης εργασίας και επόμενων ενεργειών.', refresh: 'Ανανέωση', retry: 'Δοκιμή ξανά', loadErrorTitle: 'Δεν ήταν δυνατή η δημιουργία της επισκόπησης', loadErrorDescription: 'Δοκιμάστε να ανανεώσετε τα δεδομένα.', staleData: 'Η νέα σύνοψη δεν φορτώθηκε ακόμη. Εμφανίζονται τα προηγούμενα επιβεβαιωμένα δεδομένα.', newResult: 'Νέο αποτέλεσμα', confirmedPath: 'Επιβεβαιωμένη πρόοδος', confirmedSteps: 'βήματα επιβεβαιώθηκαν με πραγματικά δεδομένα', resultsIn30Days: 'αποτελέσματα σε 30 ημέρες', activeAreas: 'τομείς ξεκίνησαν', needAttention: 'χρειάζονται προσοχή', currentPriority: 'Πιο σημαντικό τώρα', continueWorking: 'Συνεχίστε την εργασία', result: 'Αποτέλεσμα', growthAreas: 'Τομείς ανάπτυξης', growthAreasDescription: 'Ανοίξτε έναν τομέα για να δείτε τι ολοκληρώθηκε και ποιο είναι το επόμενο βήμα.', completed: 'Ολοκληρώθηκε', of: 'από', path: 'Διαδρομή', nextStepOutcome: 'Τι θα προσφέρει το επόμενο βήμα', currentAudit: 'Τρέχων έλεγχος', auditReady: 'Ο έλεγχος είναι έτοιμος', auditReadyUpdated: 'ενημερώθηκε', auditReadySuffix: 'Ανοίξτε τον για να δείτε τα στοιχεία και τις προτεραιότητες της καταχώρισης.', auditPending: 'Ο πλήρης έλεγχος θα εμφανιστεί εδώ μετά την πρώτη επιτυχημένη συλλογή δεδομένων.', viewFullAudit: 'Προβολή πλήρους ελέγχου', mapsAndReputation: 'Χάρτες και φήμη', fullAudit: 'Πλήρης έλεγχος καταχώρισης', location: 'Τοποθεσία', auditDescription: 'Δεδομένα, αιτίες προβλημάτων και συγκεκριμένες ενέργειες.', selectAuditLocation: 'Επιλέξτε τοποθεσία για έλεγχο', selectLocation: 'Επιλέξτε τοποθεσία', hideFullAudit: 'Απόκρυψη πλήρους ελέγχου', parseQueued: 'Η συλλογή δεδομένων περιμένει να ξεκινήσει. Ο τρέχων έλεγχος παραμένει διαθέσιμος.', parseProcessing: 'Συλλέγονται νέα δεδομένα. Ο τρέχων έλεγχος παραμένει στην οθόνη.', cardHistory: 'Ιστορικό ενημερώσεων καταχώρισης', recentResults: 'Πρόσφατα αποτελέσματα', recentResultsEmpty: 'Εδώ θα εμφανιστούν επιβεβαιωμένα αποτελέσματα: ολοκληρωμένος έλεγχος, πλάνο περιεχομένου, συνεργάτες, εργασίες και πρόσθετες πωλήσεις.',
};

const statusTr: Record<string, string> = {
  healthy: 'Çalışıyor',
  in_progress: 'Devam ediyor',
  needs_attention: 'Dikkat gerekiyor',
  not_started: 'Başlatılmadı',
  unavailable: 'Veri yok',
};

const areaTr: Record<string, string> = {
  maps: 'Haritalar ve itibar',
  content: 'İçerik',
  partnerships: 'İş ortakları',
  automation: 'Otomasyon',
  upsells: 'Ek satışlar',
};

const statusEl: Record<string, string> = { healthy: 'Λειτουργεί', in_progress: 'Σε εξέλιξη', needs_attention: 'Χρειάζεται προσοχή', not_started: 'Δεν ξεκίνησε', unavailable: 'Χωρίς δεδομένα' };
const areaEl: Record<string, string> = { maps: 'Χάρτες και φήμη', content: 'Περιεχόμενο', partnerships: 'Συνεργασίες', automation: 'Αυτοματοποίηση', upsells: 'Πρόσθετες πωλήσεις' };

const milestoneTr: Record<string, string> = {
  map_connected: 'Harita bağlandı',
  map_audited: 'Veriler ve denetim alındı',
  map_profile_ready: 'Temel bilgiler tamamlandı',
  map_profile_complete: 'Temel bilgiler tamamlandı',
  reputation_started: 'İtibar çalışması başladı',
  content_plan_created: 'İçerik planı oluşturuldu',
  content_draft_ready: 'İçerik hazırlandı',
  content_published: 'Yayın doğrulandı',
  partner_found: 'Potansiyel iş ortağı bulundu',
  partner_proposal_ready: 'Teklif hazırlandı',
  partner_contacted: 'İletişim kuruldu',
  partner_result: 'Yanıt veya sonuç alındı',
  agent_tested: 'Ajan test edildi',
  agent_enabled: 'Ajan etkinleştirildi',
  agent_completed: 'Çalışma görevi tamamlandı',
  upsells_calculated: 'Öneriler hesaplandı',
  upsells_enabled: 'Teklif uygulandı',
  upsells_bought: 'Satış kaydedildi',
};

const milestoneEl: Record<string, string> = {
  map_connected: 'Ο χάρτης συνδέθηκε', map_audited: 'Λήφθηκαν δεδομένα και έλεγχος', map_profile_ready: 'Συμπληρώθηκαν τα βασικά στοιχεία', map_profile_complete: 'Συμπληρώθηκαν τα βασικά στοιχεία', reputation_started: 'Ξεκίνησε η διαχείριση φήμης', content_plan_created: 'Δημιουργήθηκε πλάνο περιεχομένου', content_draft_ready: 'Ετοιμάστηκε υλικό', content_published: 'Η δημοσίευση επιβεβαιώθηκε', partner_found: 'Βρέθηκε πιθανός συνεργάτης', partner_proposal_ready: 'Ετοιμάστηκε πρόταση', partner_contacted: 'Έγινε επικοινωνία', partner_result: 'Λήφθηκε απάντηση ή αποτέλεσμα', agent_tested: 'Ο agent δοκιμάστηκε', agent_enabled: 'Ο agent ενεργοποιήθηκε', agent_completed: 'Η εργασία ολοκληρώθηκε', upsells_calculated: 'Υπολογίστηκαν προτάσεις', upsells_enabled: 'Η πρόταση εφαρμόστηκε', upsells_bought: 'Καταγράφηκε πώληση',
};

const metricTr: Record<string, string> = {
  Карты: 'Haritalar', Отзывы: 'Yorumlar', 'Без ответа': 'Yanıtsız', Планы: 'Planlar', Готово: 'Hazır', Опубликовано: 'Yayınlandı', Найдено: 'Bulundu', 'В контакте': 'İletişimde', Результаты: 'Sonuçlar', Создано: 'Oluşturuldu', Работают: 'Çalışıyor', Выполнено: 'Tamamlandı', Рассчитано: 'Hesaplandı', Внедрено: 'Uygulandı', Покупки: 'Satın almalar',
};

const metricEl: Record<string, string> = { Карты: 'Χάρτες', Отзывы: 'Κριτικές', 'Без ответа': 'Χωρίς απάντηση', Планы: 'Πλάνα', Готово: 'Έτοιμα', Опубликовано: 'Δημοσιεύτηκαν', Найдено: 'Βρέθηκαν', 'В контакте': 'Σε επικοινωνία', Результаты: 'Αποτελέσματα', Создано: 'Δημιουργήθηκαν', Работают: 'Λειτουργούν', Выполнено: 'Ολοκληρώθηκαν', Рассчитано: 'Υπολογίστηκαν', Внедрено: 'Εφαρμόστηκαν', Покупки: 'Αγορές' };

const textEl: Record<string, string> = {
  'Подключена': 'Συνδέθηκε', 'Не подключена': 'Δεν συνδέθηκε',
  'Карта подключена, но свежих данных и аудита ещё нет.': 'Ο χάρτης είναι συνδεδεμένος, αλλά δεν υπάρχουν ακόμη νέα δεδομένα ή έλεγχος.',
  'Получите данные карты': 'Λήψη δεδομένων χάρτη',
  'Появится аудит с конкретными проблемами карточки.': 'Θα εμφανιστεί έλεγχος με συγκεκριμένα προβλήματα της καταχώρισης.',
  'Обновить карту': 'Ανανέωση χάρτη',
  'Карта подключена, аудит ещё не готов': 'Ο χάρτης συνδέθηκε, ο έλεγχος δεν είναι ακόμη έτοιμος',
  'Данные временно недоступны': 'Τα δεδομένα δεν είναι προσωρινά διαθέσιμα',
  'LocalOS не смог получить состояние этого направления.': 'Το LocalOS δεν μπόρεσε να λάβει την κατάσταση αυτού του τομέα.',
  'После восстановления данных прогресс появится автоматически.': 'Η πρόοδος θα εμφανιστεί αυτόματα όταν αποκατασταθούν τα δεδομένα.',
  'Открыть раздел': 'Άνοιγμα ενότητας',
  'Проверьте состояние непосредственно в рабочем разделе.': 'Ελέγξτε την κατάσταση απευθείας στην ενότητα εργασίας.',
  'Вы увидите доступные действия и текущие данные.': 'Θα δείτε τις διαθέσιμες ενέργειες και τα τρέχοντα δεδομένα.',
  'Автоматизированные задачи ещё не настроены.': 'Δεν έχουν ρυθμιστεί ακόμη αυτοματοποιημένες εργασίες.',
  'Автоматизированных задач пока нет': 'Δεν υπάρχουν ακόμη αυτοματοποιημένες εργασίες',
  'Допродажи ещё не рассчитаны': 'Οι πρόσθετες πωλήσεις δεν έχουν ακόμη υπολογιστεί',
  'Контент-план ещё не запущен': 'Το πλάνο περιεχομένου δεν έχει ακόμη ξεκινήσει',
  'Поиск партнёров ещё не запускался': 'Η αναζήτηση συνεργατών δεν έχει ακόμη ξεκινήσει',
  'Зафиксированная дополнительная выручка': 'Καταγεγραμμένα πρόσθετα έσοδα',
};

const translateDynamicEl = (value: string) => {
  const rules: Array<[RegExp, (...values: string[]) => string]> = [
    [/^(\d+) из (\d+)$/, (completed, total) => `${completed} από ${total}`],
    [/^Планов: (\d+), готовых материалов: (\d+), опубликовано: (\d+)$/, (plans, drafts, published) => `Πλάνα: ${plans}, έτοιμο υλικό: ${drafts}, δημοσιεύτηκαν: ${published}`],
    [/^Найдено: (\d+), предложений: (\d+), результатов: (\d+)$/, (leads, proposals, results) => `Βρέθηκαν: ${leads}, προτάσεις: ${proposals}, αποτελέσματα: ${results}`],
    [/^Агентов: (\d+), работают: (\d+), выполнено задач: (\d+)$/, (agents, active, completed) => `Agents: ${agents}, ενεργοί: ${active}, ολοκληρωμένες εργασίες: ${completed}`],
    [/^Расчётов: (\d+), внедрено: (\d+), покупок: (\d+)$/, (calculated, active, bought) => `Υπολογισμοί: ${calculated}, εφαρμόστηκαν: ${active}, αγορές: ${bought}`],
    [/^Без ответа осталось отзывов: (\d+)\.$/, (count) => `Κριτικές χωρίς απάντηση: ${count}.`],
    [/^Обновлено карточек: (\d+)$/, (count) => `Ενημερωμένες καταχωρίσεις: ${count}`],
    [/^Услуг в карточке: (\d+)$/, (count) => `Υπηρεσίες στην καταχώριση: ${count}`],
    [/^Отзывов: (\d+)$/, (count) => `Κριτικές: ${count}`],
    [/^Планов: (\d+)$/, (count) => `Πλάνα: ${count}`], [/^Материалов: (\d+)$/, (count) => `Υλικά: ${count}`], [/^Публикаций: (\d+)$/, (count) => `Δημοσιεύσεις: ${count}`],
    [/^Лидов: (\d+)$/, (count) => `Πιθανοί συνεργάτες: ${count}`], [/^Предложений: (\d+)$/, (count) => `Προτάσεις: ${count}`], [/^Контактов: (\d+)$/, (count) => `Επαφές: ${count}`], [/^Результатов: (\d+)$/, (count) => `Αποτελέσματα: ${count}`],
    [/^Тестов: (\d+)$/, (count) => `Δοκιμές: ${count}`], [/^Работают: (\d+)$/, (count) => `Ενεργοί: ${count}`], [/^Расчётов: (\d+)$/, (count) => `Υπολογισμοί: ${count}`], [/^Активно: (\d+)$/, (count) => `Ενεργά: ${count}`], [/^Покупок: (\d+)$/, (count) => `Αγορές: ${count}`],
  ];
  for (const [pattern, render] of rules) { const match = value.match(pattern); if (match) return render(...match.slice(1)); }
  return value;
};

const textTr: Record<string, string> = {
  'Подключена': 'Bağlandı',
  'Не подключена': 'Bağlanmadı',
  'Данные временно недоступны': 'Veriler geçici olarak kullanılamıyor',
  'LocalOS не смог получить состояние этого направления.': 'LocalOS bu alanın durumunu alamadı.',
  'После восстановления данных прогресс появится автоматически.': 'Veriler yeniden erişilebilir olduğunda ilerleme otomatik olarak görünecek.',
  'Открыть раздел': 'Bölümü aç',
  'Проверьте состояние непосредственно в рабочем разделе.': 'Durumu doğrudan çalışma bölümünde kontrol edin.',
  'Вы увидите доступные действия и текущие данные.': 'Kullanılabilir işlemleri ve güncel verileri göreceksiniz.',
  'Без ссылки LocalOS не может проверить карточку и показать изменения.': 'Bağlantı olmadan LocalOS işletme kartını kontrol edemez ve değişiklikleri gösteremez.',
  'Подключите карту': 'Haritayı bağlayın',
  'LocalOS получит данные карточки и подготовит первый аудит.': 'LocalOS işletme kartı verilerini alacak ve ilk denetimi hazırlayacak.',
  'Добавить карту': 'Harita ekle',
  'Карточка ещё не подключена': 'İşletme kartı henüz bağlanmadı',
  'Карта подключена, но свежих данных и аудита ещё нет.': 'Harita bağlı, ancak güncel veriler ve denetim henüz yok.',
  'Получите данные карты': 'Harita verilerini alın',
  'Появится аудит с конкретными проблемами карточки.': 'İşletme kartındaki somut sorunları gösteren bir denetim oluşturulacak.',
  'Обновить карту': 'Haritayı yenile',
  'Карта подключена, аудит ещё не готов': 'Harita bağlı, denetim henüz hazır değil',
  'Ответьте на новые отзывы': 'Yeni yorumları yanıtlayın',
  'Клиенты увидят, что бизнес реагирует на обратную связь.': 'Müşteriler işletmenin geri bildirimlere yanıt verdiğini görecek.',
  'Открыть отзывы': 'Yorumları aç',
  'Аудит готов, репутация требует внимания': 'Denetim hazır, itibar dikkate ihtiyaç duyuyor',
  'В данных карты пока не хватает услуг или основных сведений.': 'Harita verilerinde hizmetler veya temel bilgiler henüz eksik.',
  'Дополните карточку': 'İşletme kartını tamamlayın',
  'Клиентам будет проще понять предложение и выбрать бизнес.': 'Müşterilerin teklifi anlaması ve işletmeyi seçmesi kolaylaşacak.',
  'Открыть рекомендации': 'Önerileri aç',
  'Аудит готов, карточку можно усилить': 'Denetim hazır, işletme kartı geliştirilebilir',
  'Поддерживайте данные актуальными': 'Verileri güncel tutun',
  'Карточка подключена, аудит доступен, срочных проблем не видно.': 'İşletme kartı bağlı, denetim erişilebilir ve acil bir sorun görünmüyor.',
  'Актуальная карточка продолжит помогать клиентам находить и выбирать бизнес.': 'Güncel işletme kartı müşterilerin işletmeyi bulmasına ve seçmesine yardımcı olmaya devam edecek.',
  'Открыть карты': 'Haritaları aç',
  'Карточка и репутация под контролем': 'İşletme kartı ve itibar kontrol altında',
  'Контент-план ещё не создан.': 'İçerik planı henüz oluşturulmadı.',
  'Запустите контент-план': 'İçerik planını başlatın',
  'Создать контент-план': 'İçerik planı oluştur',
  'План создан, но готовых материалов пока нет.': 'Plan oluşturuldu, ancak hazır içerik henüz yok.',
  'Подготовьте первый материал': 'İlk içeriği hazırlayın',
  'Открыть контент-план': 'İçerik planını aç',
  'Черновики готовы, но ни одна публикация ещё не подтверждена.': 'Taslaklar hazır, ancak henüz hiçbir yayın doğrulanmadı.',
  'Доведите материал до публикации': 'İçeriği yayına hazırlayın',
  'Проверить материалы': 'İçerikleri kontrol et',
  'Продолжайте по плану': 'Plana göre devam edin',
  'Открыть контент': 'İçeriği aç',
  'Контент-план работает, готовые материалы и публикации сохраняются в истории.': 'İçerik planı çalışıyor; hazır içerikler ve yayınlar geçmişte saklanıyor.',
  'У бизнеса будет регулярный поток подготовленных публикаций.': 'İşletme düzenli bir hazır yayın akışına sahip olacak.',
  'Контент-план ещё не запущен': 'İçerik planı henüz başlatılmadı',
  'Потенциальные партнёры ещё не найдены.': 'Potansiyel iş ortakları henüz bulunmadı.',
  'Найдите партнёров': 'İş ortakları bulun',
  'Начать поиск': 'Aramayı başlat',
  'Партнёры найдены, но предложения ещё не подготовлены.': 'İş ortakları bulundu, ancak teklifler henüz hazırlanmadı.',
  'Подготовьте предложение': 'Teklif hazırlayın',
  'Открыть партнёров': 'İş ortaklarını aç',
  'Предложения готовы и ждут следующего ручного шага.': 'Teklifler hazır ve sonraki manuel adımı bekliyor.',
  'Выберите партнёров для контакта': 'İletişim kurulacak iş ortaklarını seçin',
  'Проверить предложения': 'Teklifleri kontrol et',
  'Контакты начаты, ответы ещё не зафиксированы.': 'İletişim başladı, ancak yanıtlar henüz kaydedilmedi.',
  'Проверьте ответы и следующие шаги': 'Yanıtları ve sonraki adımları kontrol edin',
  'Открыть воронку': 'Süreci aç',
  'Развивайте успешные контакты': 'Başarılı ilişkileri geliştirin',
  'По партнёрствам уже есть подтверждённые результаты.': 'İş ortaklıklarında doğrulanmış sonuçlar var.',
  'Появятся подготовленные контакты и совместные предложения без автоматической отправки.': 'Otomatik gönderim olmadan hazırlanmış bağlantılar ve ortak teklifler oluşturulacak.',
  'Поиск партнёров ещё не запускался': 'İş ortağı araması henüz başlatılmadı',
  'Автоматизированные задачи ещё не настроены.': 'Otomatik görevler henüz yapılandırılmadı.',
  'Проверьте ошибку агента': 'Ajan hatasını kontrol edin',
  'Открыть агентов': 'Ajanları aç',
  'Настройте первую задачу': 'İlk görevi yapılandırın',
  'Создать агента': 'Ajan oluştur',
  'Агент создан, но ещё не проверен на примере.': 'Ajan oluşturuldu, ancak henüz bir örnekle test edilmedi.',
  'Запустите безопасный тест': 'Güvenli testi başlatın',
  'Проверить агента': 'Ajanı test et',
  'Тест пройден, но ни один агент не включён в работу.': 'Test tamamlandı, ancak hiçbir ajan çalışmak üzere etkinleştirilmedi.',
  'Включите проверенного агента': 'Test edilen ajanı etkinleştirin',
  'Агент включён, но рабочего результата пока нет.': 'Ajan etkin, ancak henüz bir çalışma sonucu yok.',
  'Запустите первую работу': 'İlk çalışmayı başlatın',
  'Следите за следующими результатами': 'Sonraki sonuçları takip edin',
  'Агенты выполняют рабочие задачи, результаты сохраняются в истории.': 'Ajanlar çalışma görevlerini yürütüyor ve sonuçlar geçmişte saklanıyor.',
  'Повторяемая работа будет выполняться без повторной настройки сценария.': 'Tekrarlanan işler senaryoyu yeniden yapılandırmadan yürütülecek.',
  'Автоматизированных задач пока нет': 'Henüz otomatik görev yok',
  'Варианты допродаж ещё не рассчитаны.': 'Ek satış seçenekleri henüz hesaplanmadı.',
  'Рассчитайте допродажи': 'Ek satışları hesaplayın',
  'Рассчитать допродажи': 'Ek satışları hesapla',
  'Рекомендации рассчитаны, но ни одна не включена в работу.': 'Öneriler hesaplandı, ancak hiçbiri uygulamaya alınmadı.',
  'Выберите предложения для внедрения': 'Uygulanacak teklifleri seçin',
  'Предложения внедрены, продажи по ним ещё не зафиксированы.': 'Teklifler uygulandı, ancak bunlardan gelen satışlar henüz kaydedilmedi.',
  'Начните отмечать результаты': 'Sonuçları kaydetmeye başlayın',
  'Открыть допродажи': 'Ek satışları aç',
  'Продолжайте фиксировать результаты': 'Sonuçları kaydetmeye devam edin',
  'По внедрённым предложениям уже зафиксированы покупки.': 'Uygulanan teklifler için satın almalar kaydedildi.',
  'Сотрудникам будет понятно, что уместно предложить вместе с основной услугой.': 'Çalışanlar ana hizmetle birlikte ne önereceklerini bilecek.',
  'Допродажи ещё не рассчитаны': 'Ek satışlar henüz hesaplanmadı',
  'Зафиксированная дополнительная выручка': 'Kaydedilen ek gelir',
  'Оптимизация услуг применена': 'Hizmet optimizasyonu uygulandı',
  'Публикация подтверждена': 'Yayın doğrulandı',
  'Изменение карточки подтверждено': 'İşletme kartı değişikliği doğrulandı',
  'В карточке обнаружено внешнее изменение': 'İşletme kartında dış değişiklik algılandı',
  'Подтверждённое действие': 'Doğrulanmış işlem',
  'Изменение найдено по новому снимку; LocalOS не приписывает его себе.': 'Değişiklik yeni görüntüde bulundu; LocalOS bunu kendi işlemi olarak göstermez.',
  'Действие сохранено с источником и будет сопоставлено с последующими метриками.': 'İşlem kaynağıyla birlikte kaydedildi ve sonraki metriklerle karşılaştırılacak.',
};

const translateDynamicTr = (value: string) => {
  const rules: Array<[RegExp, (...values: string[]) => string]> = [
    [/^(\d+) из (\d+)$/, (completed, total) => `${completed} / ${total}`],
    [/^Точка «(.+)»: без ответа осталось отзывов: (\d+)\.$/, (location, count) => `“${location}” konumunda yanıtsız yorum: ${count}.`],
    [/^Без ответа осталось отзывов: (\d+)\.$/, (count) => `Yanıtsız yorum: ${count}.`],
    [/^Рабочих запусков с ошибкой: (\d+)\.$/, (count) => `Hatalı çalışma sayısı: ${count}.`],
    [/^Планов: (\d+), готовых материалов: (\d+), опубликовано: (\d+)$/, (plans, drafts, published) => `Plan: ${plans}, hazır içerik: ${drafts}, yayınlanan: ${published}`],
    [/^Найдено: (\d+), предложений: (\d+), результатов: (\d+)$/, (leads, proposals, results) => `Bulunan: ${leads}, teklif: ${proposals}, sonuç: ${results}`],
    [/^Агентов: (\d+), работают: (\d+), выполнено задач: (\d+)$/, (agents, active, completed) => `Ajan: ${agents}, çalışan: ${active}, tamamlanan görev: ${completed}`],
    [/^Расчётов: (\d+), внедрено: (\d+), покупок: (\d+)$/, (calculated, active, bought) => `Hesaplanan: ${calculated}, uygulanan: ${active}, satın alma: ${bought}`],
    [/^Обновлено карточек: (\d+)$/, (count) => `Güncellenen kart: ${count}`],
    [/^Услуг в карточке: (\d+)$/, (count) => `Karttaki hizmet: ${count}`],
    [/^Отзывов: (\d+)$/, (count) => `Yorum: ${count}`],
    [/^Планов: (\d+)$/, (count) => `Plan: ${count}`],
    [/^Материалов: (\d+)$/, (count) => `İçerik: ${count}`],
    [/^Публикаций: (\d+)$/, (count) => `Yayın: ${count}`],
    [/^Лидов: (\d+)$/, (count) => `Potansiyel ortak: ${count}`],
    [/^Предложений: (\d+)$/, (count) => `Teklif: ${count}`],
    [/^Контактов: (\d+)$/, (count) => `İletişim: ${count}`],
    [/^Результатов: (\d+)$/, (count) => `Sonuç: ${count}`],
    [/^Тестов: (\d+)$/, (count) => `Test: ${count}`],
    [/^Работают: (\d+)$/, (count) => `Çalışan: ${count}`],
    [/^Расчётов: (\d+)$/, (count) => `Hesaplama: ${count}`],
    [/^Активно: (\d+)$/, (count) => `Etkin: ${count}`],
    [/^Покупок: (\d+)$/, (count) => `Satın alma: ${count}`],
  ];
  for (const [pattern, render] of rules) {
    const match = value.match(pattern);
    if (match) return render(...match.slice(1));
  }
  return value;
};

export const progressPageCopyForLanguage = (language: Language) => language === 'tr' ? tr : language === 'el' ? el : ru;

export const localizedGrowthStatus = (language: Language, status: string, fallback: string) => (
  language === 'tr' ? statusTr[status] || fallback : language === 'el' ? statusEl[status] || fallback : fallback
);

export const localizedGrowthArea = (language: Language, key: string, fallback: string) => (
  language === 'tr' ? areaTr[key] || fallback : language === 'el' ? areaEl[key] || fallback : fallback
);

export const localizedGrowthMilestone = (language: Language, key: string, fallback: string) => (
  language === 'tr' ? milestoneTr[key] || fallback : language === 'el' ? milestoneEl[key] || fallback : fallback
);

export const localizedGrowthMetric = (language: Language, fallback: string) => (
  language === 'tr' ? metricTr[fallback] || translateDynamicTr(fallback) : language === 'el' ? metricEl[fallback] || translateDynamicEl(fallback) : fallback
);

export const localizedGrowthText = (language: Language, value?: string | null) => {
  const normalized = String(value || '').trim();
  if (!normalized) return normalized;
  if (language === 'tr') return textTr[normalized] || translateDynamicTr(normalized);
  if (language === 'el') return textEl[normalized] || translateDynamicEl(normalized);
  return normalized;
};

export const localizedProgressBusinessName = (language: Language, value?: string | null) => {
  const normalized = String(value || '').trim();
  if ((language === 'tr' || language === 'el') && normalized.toLowerCase() === 'рога и копыта') return 'Roga i Kopyta';
  return normalized;
};
