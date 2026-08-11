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

type ProgressLabels = {
  eyebrow: string; title: string; description: string; select: string; loading: string; refresh: string; retry: string; error: string;
  stale: string; confirmed: string; steps: string; results: string; areas: string; attention: string; priority: string; outcome: string;
  growth: string; growthDescription: string; completed: string; of: string; path: string; audit: string; location: string; recent: string; empty: string;
};

const buildProgressCopy = (value: ProgressLabels): ProgressPageCopy => ({
  eyebrow: value.eyebrow, title: value.title, description: value.description, selectBusinessDescription: value.select,
  loadingDescription: value.loading, fallbackDescription: value.description, refresh: value.refresh, retry: value.retry,
  loadErrorTitle: value.error, loadErrorDescription: value.retry, staleData: value.stale, newResult: value.results,
  confirmedPath: value.confirmed, confirmedSteps: value.steps, resultsIn30Days: value.results, activeAreas: value.areas,
  needAttention: value.attention, currentPriority: value.priority, continueWorking: value.growthDescription, result: value.outcome,
  growthAreas: value.growth, growthAreasDescription: value.growthDescription, completed: value.completed, of: value.of, path: value.path,
  nextStepOutcome: value.outcome, currentAudit: value.audit, auditReady: value.audit, auditReadyUpdated: value.refresh,
  auditReadySuffix: value.growthDescription, auditPending: value.loading, viewFullAudit: value.audit, mapsAndReputation: value.growth,
  fullAudit: value.audit, location: value.location, auditDescription: value.growthDescription, selectAuditLocation: value.select,
  selectLocation: value.select, hideFullAudit: value.audit, parseQueued: value.loading, parseProcessing: value.loading,
  cardHistory: value.path, recentResults: value.recent, recentResultsEmpty: value.empty,
});

const en = buildProgressCopy({ eyebrow: 'BUSINESS OVERVIEW', title: 'Business progress', description: 'See what is complete, where help is needed, and which step will produce the next practical result.', select: 'Select a business to see its progress and next step.', loading: 'Collecting confirmed results from LocalOS workspaces.', refresh: 'Refresh', retry: 'Try again', error: 'Could not build the overview', stale: 'The new summary is not ready. Previous confirmed data is shown.', confirmed: 'Confirmed path', steps: 'steps confirmed by real data', results: 'results in 30 days', areas: 'areas started', attention: 'need attention', priority: 'Most important now', outcome: 'Result of the next step', growth: 'Growth areas', growthDescription: 'Open an area to see completed work and the next action.', completed: 'Completed', of: 'of', path: 'Path', audit: 'Full listing audit', location: 'Location', recent: 'Recent results', empty: 'Confirmed audits, content plans, partners, completed work, and upsells will appear here.' });
const fr = buildProgressCopy({ eyebrow: 'VUE D’ENSEMBLE', title: 'Progression de l’entreprise', description: 'Voyez ce qui est terminé, où une aide est nécessaire et quelle étape produira le prochain résultat concret.', select: 'Sélectionnez une entreprise pour voir sa progression et l’étape suivante.', loading: 'Collecte des résultats confirmés dans LocalOS.', refresh: 'Actualiser', retry: 'Réessayer', error: 'Impossible de créer la vue d’ensemble', stale: 'Le nouveau résumé n’est pas prêt. Les dernières données confirmées sont affichées.', confirmed: 'Parcours confirmé', steps: 'étapes confirmées par des données réelles', results: 'résultats sur 30 jours', areas: 'axes commencés', attention: 'demandent votre attention', priority: 'Priorité actuelle', outcome: 'Résultat de l’étape suivante', growth: 'Axes de croissance', growthDescription: 'Ouvrez un axe pour voir le travail terminé et l’action suivante.', completed: 'Terminé', of: 'sur', path: 'Parcours', audit: 'Audit complet de la fiche', location: 'Point de vente', recent: 'Résultats récents', empty: 'Les audits, plans de contenu, partenaires, travaux terminés et ventes additionnelles apparaîtront ici.' });
const es = buildProgressCopy({ eyebrow: 'RESUMEN DEL NEGOCIO', title: 'Progreso del negocio', description: 'Consulta qué está terminado, dónde hace falta ayuda y qué paso dará el siguiente resultado práctico.', select: 'Selecciona un negocio para ver su progreso y siguiente paso.', loading: 'Recopilando resultados confirmados de LocalOS.', refresh: 'Actualizar', retry: 'Reintentar', error: 'No se pudo crear el resumen', stale: 'El nuevo resumen aún no está listo. Se muestran los datos confirmados anteriores.', confirmed: 'Ruta confirmada', steps: 'pasos confirmados con datos reales', results: 'resultados en 30 días', areas: 'áreas iniciadas', attention: 'requieren atención', priority: 'Lo más importante ahora', outcome: 'Resultado del siguiente paso', growth: 'Áreas de crecimiento', growthDescription: 'Abre un área para ver el trabajo realizado y la siguiente acción.', completed: 'Completado', of: 'de', path: 'Ruta', audit: 'Auditoría completa de la ficha', location: 'Ubicación', recent: 'Resultados recientes', empty: 'Aquí aparecerán auditorías, planes de contenido, socios, trabajos terminados y ventas adicionales.' });
const de = buildProgressCopy({ eyebrow: 'GESCHÄFTSÜBERBLICK', title: 'Geschäftsfortschritt', description: 'Sehen Sie, was erledigt ist, wo Hilfe nötig ist und welcher Schritt das nächste praktische Ergebnis bringt.', select: 'Wählen Sie ein Unternehmen, um Fortschritt und nächsten Schritt zu sehen.', loading: 'Bestätigte Ergebnisse aus LocalOS werden gesammelt.', refresh: 'Aktualisieren', retry: 'Erneut versuchen', error: 'Übersicht konnte nicht erstellt werden', stale: 'Die neue Zusammenfassung ist noch nicht bereit. Vorherige bestätigte Daten werden angezeigt.', confirmed: 'Bestätigter Weg', steps: 'Schritte durch echte Daten bestätigt', results: 'Ergebnisse in 30 Tagen', areas: 'Bereiche begonnen', attention: 'brauchen Aufmerksamkeit', priority: 'Jetzt am wichtigsten', outcome: 'Ergebnis des nächsten Schritts', growth: 'Wachstumsbereiche', growthDescription: 'Öffnen Sie einen Bereich, um erledigte Arbeit und die nächste Aktion zu sehen.', completed: 'Erledigt', of: 'von', path: 'Weg', audit: 'Vollständiges Eintragsaudit', location: 'Standort', recent: 'Letzte Ergebnisse', empty: 'Audits, Content-Pläne, Partner, erledigte Arbeiten und Zusatzverkäufe erscheinen hier.' });
const th = buildProgressCopy({ eyebrow: 'ภาพรวมธุรกิจ', title: 'ความคืบหน้าของธุรกิจ', description: 'ดูสิ่งที่เสร็จ จุดที่ต้องช่วย และขั้นต่อไปที่จะให้ผลจริง', select: 'เลือกธุรกิจเพื่อดูความคืบหน้าและขั้นต่อไป', loading: 'กำลังรวบรวมผลลัพธ์ที่ยืนยันแล้ว', refresh: 'รีเฟรช', retry: 'ลองใหม่', error: 'สร้างภาพรวมไม่ได้', stale: 'สรุปใหม่ยังไม่พร้อม กำลังแสดงข้อมูลที่ยืนยันก่อนหน้า', confirmed: 'เส้นทางที่ยืนยัน', steps: 'ขั้นที่ยืนยันด้วยข้อมูลจริง', results: 'ผลลัพธ์ใน 30 วัน', areas: 'ด้านที่เริ่มแล้ว', attention: 'ต้องดูแล', priority: 'สำคัญที่สุดตอนนี้', outcome: 'ผลของขั้นต่อไป', growth: 'ด้านการเติบโต', growthDescription: 'เปิดแต่ละด้านเพื่อดูงานที่เสร็จและขั้นต่อไป', completed: 'เสร็จ', of: 'จาก', path: 'เส้นทาง', audit: 'ตรวจสอบรายการแบบเต็ม', location: 'สาขา', recent: 'ผลลัพธ์ล่าสุด', empty: 'ผลที่ยืนยันแล้วจะแสดงที่นี่' });
const ar = buildProgressCopy({ eyebrow: 'نظرة عامة على العمل', title: 'تقدم العمل', description: 'شاهد ما اكتمل وأين تلزم المساعدة والخطوة التي ستحقق النتيجة التالية.', select: 'اختر نشاطًا لرؤية التقدم والخطوة التالية.', loading: 'جارٍ جمع النتائج المؤكدة.', refresh: 'تحديث', retry: 'إعادة المحاولة', error: 'تعذر إنشاء النظرة العامة', stale: 'الملخص الجديد غير جاهز. تظهر البيانات المؤكدة السابقة.', confirmed: 'المسار المؤكد', steps: 'خطوات مؤكدة ببيانات حقيقية', results: 'نتائج في 30 يومًا', areas: 'مجالات بدأت', attention: 'تحتاج انتباهًا', priority: 'الأهم الآن', outcome: 'نتيجة الخطوة التالية', growth: 'مجالات النمو', growthDescription: 'افتح مجالًا لرؤية العمل المنجز والإجراء التالي.', completed: 'مكتمل', of: 'من', path: 'المسار', audit: 'تدقيق كامل للبطاقة', location: 'الموقع', recent: 'النتائج الأخيرة', empty: 'ستظهر هنا النتائج المؤكدة.' });
const ha = buildProgressCopy({ eyebrow: 'BAYANIN KASUWANCI', title: 'Ci gaban kasuwanci', description: 'Duba abin da aka gama, inda ake buƙatar taimako da matakin da zai kawo sakamako na gaba.', select: 'Zaɓi kasuwanci don ganin ci gaba da mataki na gaba.', loading: 'Ana tattara sakamakon da aka tabbatar.', refresh: 'Sabunta', retry: 'Sake gwadawa', error: 'Ba a iya gina bayanin ba', stale: 'Sabon taƙaitaccen bayani bai shirya ba. Ana nuna bayanan da aka tabbatar a baya.', confirmed: 'Hanyar da aka tabbatar', steps: 'matakai da aka tabbatar da bayanai', results: 'sakamako cikin kwanaki 30', areas: 'wuraren da aka fara', attention: 'suna buƙatar kulawa', priority: 'Mafi muhimmanci yanzu', outcome: 'Sakamakon mataki na gaba', growth: 'Wuraren bunƙasa', growthDescription: 'Buɗe wuri don ganin aikin da aka gama da mataki na gaba.', completed: 'An gama', of: 'cikin', path: 'Hanya', audit: 'Cikakken binciken kati', location: 'Wuri', recent: 'Sakamako na baya-bayan nan', empty: 'Sakamakon da aka tabbatar zai bayyana a nan.' });

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

const progressCopies: Record<Language, ProgressPageCopy> = { ru, en, fr, es, el, de, th, ar, ha, tr };

const genericText: Record<Exclude<Language, 'ru'>, string> = {
  en: 'Open this area to see the current details and next action.',
  fr: 'Ouvrez cette section pour voir la situation actuelle et l’action suivante.',
  es: 'Abre esta sección para ver el estado actual y la siguiente acción.',
  el: 'Ανοίξτε αυτή την ενότητα για να δείτε την τρέχουσα κατάσταση και την επόμενη ενέργεια.',
  de: 'Öffnen Sie diesen Bereich, um den aktuellen Stand und die nächste Aktion zu sehen.',
  th: 'เปิดส่วนนี้เพื่อดูสถานะปัจจุบันและขั้นตอนถัดไป',
  ar: 'افتح هذا القسم لرؤية الحالة الحالية والإجراء التالي.',
  ha: 'Buɗe wannan sashe don ganin halin yanzu da mataki na gaba.',
  tr: 'Güncel durumu ve sonraki adımı görmek için bu alanı açın.',
};

const statuses: Record<Exclude<Language, 'ru'>, Record<string, string>> = {
  en: { healthy: 'Working', in_progress: 'In progress', needs_attention: 'Needs attention', not_started: 'Not started', unavailable: 'No data' },
  fr: { healthy: 'Opérationnel', in_progress: 'En cours', needs_attention: 'À vérifier', not_started: 'Non commencé', unavailable: 'Sans données' },
  es: { healthy: 'En funcionamiento', in_progress: 'En curso', needs_attention: 'Requiere atención', not_started: 'Sin iniciar', unavailable: 'Sin datos' },
  el: statusEl,
  de: { healthy: 'Aktiv', in_progress: 'In Arbeit', needs_attention: 'Aufmerksamkeit nötig', not_started: 'Nicht begonnen', unavailable: 'Keine Daten' },
  th: { healthy: 'ทำงานอยู่', in_progress: 'กำลังดำเนินการ', needs_attention: 'ต้องดูแล', not_started: 'ยังไม่เริ่ม', unavailable: 'ไม่มีข้อมูล' },
  ar: { healthy: 'يعمل', in_progress: 'قيد التنفيذ', needs_attention: 'يحتاج إلى اهتمام', not_started: 'لم يبدأ', unavailable: 'لا توجد بيانات' },
  ha: { healthy: 'Yana aiki', in_progress: 'Ana aiki', needs_attention: 'Yana buƙatar kulawa', not_started: 'Ba a fara ba', unavailable: 'Babu bayanai' },
  tr: statusTr,
};

const areas: Record<Exclude<Language, 'ru'>, Record<string, string>> = {
  en: { maps: 'Maps and reputation', content: 'Content', partnerships: 'Partnerships', automation: 'Automation', upsells: 'Upsells' },
  fr: { maps: 'Cartes et réputation', content: 'Contenu', partnerships: 'Partenariats', automation: 'Automatisation', upsells: 'Ventes additionnelles' },
  es: { maps: 'Mapas y reputación', content: 'Contenido', partnerships: 'Alianzas', automation: 'Automatización', upsells: 'Ventas adicionales' },
  el: areaEl,
  de: { maps: 'Karten und Ruf', content: 'Inhalte', partnerships: 'Partnerschaften', automation: 'Automatisierung', upsells: 'Zusatzverkäufe' },
  th: { maps: 'แผนที่และชื่อเสียง', content: 'เนื้อหา', partnerships: 'พันธมิตร', automation: 'ระบบอัตโนมัติ', upsells: 'ยอดขายเพิ่มเติม' },
  ar: { maps: 'الخرائط والسمعة', content: 'المحتوى', partnerships: 'الشراكات', automation: 'الأتمتة', upsells: 'المبيعات الإضافية' },
  ha: { maps: 'Taswirori da suna', content: 'Abun ciki', partnerships: 'Haɗin gwiwa', automation: 'Aiki ta atomatik', upsells: 'Ƙarin tallace-tallace' },
  tr: areaTr,
};

const runtimeCopy: Record<Language, { analytics: string; inProgress: string; nextLevel: string; rhythm: string; ready: string; update: string; needsData: string; networkLocations: string; attention: string; healthy: string; networkLocation: string }> = {
  ru: { analytics: 'Аналитика', inProgress: 'в процессе', nextLevel: 'Следующий уровень', rhythm: 'Ритм', ready: 'готово', update: 'обновить', needsData: 'нужны данные', networkLocations: 'точек в сети', attention: 'требуют внимания', healthy: 'без открытых проблем', networkLocation: 'Точка сети' },
  en: { analytics: 'Analytics', inProgress: 'in progress', nextLevel: 'Next level', rhythm: 'Rhythm', ready: 'ready', update: 'update', needsData: 'data needed', networkLocations: 'network locations', attention: 'need attention', healthy: 'without open issues', networkLocation: 'Network location' },
  fr: { analytics: 'Analytique', inProgress: 'en cours', nextLevel: 'Niveau suivant', rhythm: 'Rythme', ready: 'prêt', update: 'actualiser', needsData: 'données requises', networkLocations: 'points du réseau', attention: 'à vérifier', healthy: 'sans problème ouvert', networkLocation: 'Point du réseau' },
  es: { analytics: 'Analítica', inProgress: 'en curso', nextLevel: 'Siguiente nivel', rhythm: 'Ritmo', ready: 'listo', update: 'actualizar', needsData: 'faltan datos', networkLocations: 'ubicaciones de la red', attention: 'requieren atención', healthy: 'sin problemas abiertos', networkLocation: 'Ubicación de red' },
  el: { analytics: 'Αναλυτικά', inProgress: 'σε εξέλιξη', nextLevel: 'Επόμενο επίπεδο', rhythm: 'Ρυθμός', ready: 'έτοιμο', update: 'ενημέρωση', needsData: 'χρειάζονται δεδομένα', networkLocations: 'σημεία δικτύου', attention: 'χρειάζονται προσοχή', healthy: 'χωρίς ανοικτά προβλήματα', networkLocation: 'Σημείο δικτύου' },
  de: { analytics: 'Analyse', inProgress: 'in Arbeit', nextLevel: 'Nächste Stufe', rhythm: 'Rhythmus', ready: 'bereit', update: 'aktualisieren', needsData: 'Daten benötigt', networkLocations: 'Netzwerkstandorte', attention: 'brauchen Aufmerksamkeit', healthy: 'ohne offene Probleme', networkLocation: 'Netzwerkstandort' },
  th: { analytics: 'การวิเคราะห์', inProgress: 'กำลังดำเนินการ', nextLevel: 'ระดับถัดไป', rhythm: 'จังหวะ', ready: 'พร้อม', update: 'อัปเดต', needsData: 'ต้องมีข้อมูล', networkLocations: 'สาขาในเครือข่าย', attention: 'ต้องดูแล', healthy: 'ไม่มีปัญหาค้างอยู่', networkLocation: 'สาขาในเครือข่าย' },
  ar: { analytics: 'التحليلات', inProgress: 'قيد التنفيذ', nextLevel: 'المستوى التالي', rhythm: 'الإيقاع', ready: 'جاهز', update: 'تحديث', needsData: 'تحتاج بيانات', networkLocations: 'مواقع الشبكة', attention: 'تحتاج إلى اهتمام', healthy: 'دون مشكلات مفتوحة', networkLocation: 'موقع الشبكة' },
  ha: { analytics: 'Nazari', inProgress: 'ana aiki', nextLevel: 'Mataki na gaba', rhythm: 'Tsari', ready: 'a shirye', update: 'sabunta', needsData: 'ana buƙatar bayanai', networkLocations: 'wuraren cibiyar', attention: 'suna buƙatar kulawa', healthy: 'ba matsala a buɗe', networkLocation: 'Wurin cibiyar' },
  tr: { analytics: 'Analiz', inProgress: 'devam ediyor', nextLevel: 'Sonraki seviye', rhythm: 'Ritim', ready: 'hazır', update: 'güncelle', needsData: 'veri gerekli', networkLocations: 'ağ konumu', attention: 'dikkat gerektiriyor', healthy: 'açık sorun yok', networkLocation: 'Ağ konumu' },
};

export const progressPageCopyForLanguage = (language: Language) => progressCopies[language];
export const progressRuntimeCopyForLanguage = (language: Language) => runtimeCopy[language];

export const localizedGrowthStatus = (language: Language, status: string, fallback: string) => (
  language === 'ru' ? fallback : statuses[language][status] || genericText[language]
);

export const localizedGrowthArea = (language: Language, key: string, fallback: string) => (
  language === 'ru' ? fallback : areas[language][key] || genericText[language]
);

export const localizedGrowthMilestone = (language: Language, key: string, fallback: string) => (
  language === 'tr' ? milestoneTr[key] || genericText.tr : language === 'el' ? milestoneEl[key] || genericText.el : language === 'ru' ? fallback : genericText[language]
);

export const localizedGrowthMetric = (language: Language, fallback: string) => (
  language === 'tr' ? metricTr[fallback] || translateDynamicTr(fallback) : language === 'el' ? metricEl[fallback] || translateDynamicEl(fallback) : language === 'ru' ? fallback : /[А-Яа-яЁё]/.test(fallback) ? genericText[language] : fallback
);

export const localizedGrowthText = (language: Language, value?: string | null) => {
  const normalized = String(value || '').trim();
  if (!normalized) return normalized;
  if (language === 'tr') return textTr[normalized] || translateDynamicTr(normalized);
  if (language === 'el') return textEl[normalized] || translateDynamicEl(normalized);
  if (language !== 'ru' && /[А-Яа-яЁё]/.test(normalized)) return genericText[language];
  return normalized;
};

export const localizedProgressBusinessName = (language: Language, value?: string | null) => {
  const normalized = String(value || '').trim();
  if (language !== 'ru' && normalized.toLowerCase() === 'рога и копыта') return 'Roga i Kopyta';
  return normalized;
};
