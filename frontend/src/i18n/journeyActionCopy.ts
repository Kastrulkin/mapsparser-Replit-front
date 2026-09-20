import type { Language } from './LanguageContext.logic';

export type JourneyActionCopy = {
  now: string;
  due: string;
  replyOutcomeLabel: string;
  saveError: string;
  publicationUrl: string;
  termsOrComment: string;
  reviewDraft: string;
  publicationDate: string;
  assignTask: string;
  expectedResult: string;
  defaultExpectedResult: string;
  runInstructions: string;
  confirmedResult: string;
  inquiries: string;
  sales: string;
  views: string;
  copy: string;
  noReplyFollowup: string;
  commands: Record<string, string>;
  outcomes: Record<'interested' | 'paid' | 'barter' | 'details' | 'refused' | 'other', string>;
  useCases: Record<'reviews_without_reply' | 'content_drafts' | 'map_changes' | 'weekly_summary', string>;
};

const commands = {
  mark_sent: 'Сообщение отправлено', record_reply: 'Сохранить ответ', prepare_followup: 'Подготовить follow-up',
  save_terms: 'Сохранить условия', mark_launched: 'Партнёрство запущено', mark_published: 'Размещение вышло',
  add_result: 'Добавить результат', complete: 'Готово', start_next_cycle: 'Начать следующий цикл', open_upgrade: 'Выбрать тариф',
  prepare: 'Подготовить черновик', save_draft: 'Сохранить черновик', schedule: 'Добавить в календарь',
  refresh: 'Обновить данные', retry_refresh: 'Повторить обновление', save_configuration: 'Сохранить настройку',
  approve: 'Подтвердить план', link_run: 'Проверить завершённый запуск',
};

const outcomes = { interested: 'Интересно', paid: 'Просит оплату', barter: 'Готов на бартер', details: 'Нужны детали', refused: 'Отказал', other: 'Другое' };
const useCases = { reviews_without_reply: 'Собирать отзывы без ответа', content_drafts: 'Готовить черновики контента', map_changes: 'Проверять изменения карточек', weekly_summary: 'Собирать недельную сводку' };

const copy: Record<Language, JourneyActionCopy> = {
  ru: {
    now: 'Что сделать сейчас', due: 'Срок', replyOutcomeLabel: 'Результат ответа', saveError: 'Не удалось сохранить действие', publicationUrl: 'Ссылка на публикацию', termsOrComment: 'Условия или комментарий', reviewDraft: 'Проверьте и отредактируйте черновик', publicationDate: 'Дата публикации', assignTask: 'Что поручить', expectedResult: 'Что должно получиться', defaultExpectedResult: 'Подготовленные материалы для проверки', runInstructions: 'Настройте и запустите ИИ-сотрудника в рабочей области ниже. Затем вернитесь к этому шагу и нажмите «Проверить завершённый запуск».', confirmedResult: 'Что подтверждено результатом запуска', inquiries: 'Обращения', sales: 'Продажи', views: 'Просмотры', copy: 'Скопировать', noReplyFollowup: 'Ответа нет — follow-up', commands, outcomes, useCases,
  },
  en: {
    now: 'What to do now', due: 'Due', replyOutcomeLabel: 'Reply outcome', saveError: 'Could not save the action', publicationUrl: 'Publication link', termsOrComment: 'Terms or comment', reviewDraft: 'Review and edit the draft', publicationDate: 'Publication date', assignTask: 'Assign a task', expectedResult: 'Expected result', defaultExpectedResult: 'Prepared materials for review', runInstructions: 'Set up and run the AI assistant in the workspace below. Then return to this step and select “Check completed run”.', confirmedResult: 'What the run result confirmed', inquiries: 'Enquiries', sales: 'Sales', views: 'Views', copy: 'Copy', noReplyFollowup: 'No reply — prepare follow-up',
    commands: { mark_sent: 'Message marked as sent', record_reply: 'Save reply', prepare_followup: 'Prepare follow-up', save_terms: 'Save terms', mark_launched: 'Partnership marked as launched', mark_published: 'Placement marked as published', add_result: 'Add result', complete: 'Done', start_next_cycle: 'Start next cycle', open_upgrade: 'Choose plan', prepare: 'Prepare draft', save_draft: 'Save draft', schedule: 'Add to calendar', refresh: 'Refresh data', retry_refresh: 'Retry refresh', save_configuration: 'Save setup', approve: 'Confirm plan', link_run: 'Check completed run' },
    outcomes: { interested: 'Interested', paid: 'Requests payment', barter: 'Open to barter', details: 'Needs details', refused: 'Declined', other: 'Other' },
    useCases: { reviews_without_reply: 'Collect reviews without replies', content_drafts: 'Prepare content drafts', map_changes: 'Check listing changes', weekly_summary: 'Prepare a weekly summary' },
  },
  es: {
    now: 'Qué hacer ahora', due: 'Fecha límite', replyOutcomeLabel: 'Resultado de la respuesta', saveError: 'No se pudo guardar la acción', publicationUrl: 'Enlace a la publicación', termsOrComment: 'Condiciones o comentario', reviewDraft: 'Revisa y edita el borrador', publicationDate: 'Fecha de publicación', assignTask: 'Qué asignar', expectedResult: 'Resultado esperado', defaultExpectedResult: 'Materiales preparados para revisión', runInstructions: 'Configura e inicia el asistente de IA en el espacio de trabajo de abajo. Luego vuelve a este paso y selecciona «Comprobar ejecución terminada».', confirmedResult: 'Lo que confirmó el resultado de la ejecución', inquiries: 'Consultas', sales: 'Ventas', views: 'Vistas', copy: 'Copiar', noReplyFollowup: 'Sin respuesta — preparar seguimiento',
    commands: { mark_sent: 'Mensaje marcado como enviado', record_reply: 'Guardar respuesta', prepare_followup: 'Preparar seguimiento', save_terms: 'Guardar condiciones', mark_launched: 'Colaboración marcada como iniciada', mark_published: 'Publicación marcada como publicada', add_result: 'Añadir resultado', complete: 'Listo', start_next_cycle: 'Iniciar el siguiente ciclo', open_upgrade: 'Elegir plan', prepare: 'Preparar borrador', save_draft: 'Guardar borrador', schedule: 'Añadir al calendario', refresh: 'Actualizar datos', retry_refresh: 'Reintentar actualización', save_configuration: 'Guardar configuración', approve: 'Confirmar plan', link_run: 'Comprobar ejecución terminada' },
    outcomes: { interested: 'Interesado', paid: 'Solicita pago', barter: 'Abierto al trueque', details: 'Necesita detalles', refused: 'Rechazó', other: 'Otro' },
    useCases: { reviews_without_reply: 'Recopilar reseñas sin respuesta', content_drafts: 'Preparar borradores de contenido', map_changes: 'Comprobar cambios en la ficha', weekly_summary: 'Preparar resumen semanal' },
  },
  fr: {
    now: 'À faire maintenant', due: 'Échéance', replyOutcomeLabel: 'Résultat de la réponse', saveError: 'Impossible d’enregistrer l’action', publicationUrl: 'Lien vers la publication', termsOrComment: 'Conditions ou commentaire', reviewDraft: 'Vérifiez et modifiez le brouillon', publicationDate: 'Date de publication', assignTask: 'Tâche à confier', expectedResult: 'Résultat attendu', defaultExpectedResult: 'Documents préparés pour vérification', runInstructions: 'Configurez et lancez l’assistant IA dans l’espace de travail ci-dessous. Revenez ensuite à cette étape et choisissez « Vérifier l’exécution terminée ».', confirmedResult: 'Ce que le résultat d’exécution a confirmé', inquiries: 'Demandes', sales: 'Ventes', views: 'Vues', copy: 'Copier', noReplyFollowup: 'Pas de réponse — préparer une relance',
    commands: { mark_sent: 'Message marqué comme envoyé', record_reply: 'Enregistrer la réponse', prepare_followup: 'Préparer une relance', save_terms: 'Enregistrer les conditions', mark_launched: 'Partenariat marqué comme lancé', mark_published: 'Publication marquée comme sortie', add_result: 'Ajouter un résultat', complete: 'Terminé', start_next_cycle: 'Démarrer le cycle suivant', open_upgrade: 'Choisir une offre', prepare: 'Préparer un brouillon', save_draft: 'Enregistrer le brouillon', schedule: 'Ajouter au calendrier', refresh: 'Actualiser les données', retry_refresh: 'Réessayer l’actualisation', save_configuration: 'Enregistrer la configuration', approve: 'Confirmer le plan', link_run: 'Vérifier l’exécution terminée' },
    outcomes: { interested: 'Intéressé', paid: 'Demande un paiement', barter: 'Ouvert au troc', details: 'Demande des précisions', refused: 'Refusé', other: 'Autre' },
    useCases: { reviews_without_reply: 'Recueillir les avis sans réponse', content_drafts: 'Préparer des brouillons de contenu', map_changes: 'Vérifier les changements de fiche', weekly_summary: 'Préparer le résumé hebdomadaire' },
  },
  el: {
    now: 'Τι να κάνετε τώρα', due: 'Προθεσμία', replyOutcomeLabel: 'Αποτέλεσμα απάντησης', saveError: 'Δεν ήταν δυνατή η αποθήκευση της ενέργειας', publicationUrl: 'Σύνδεσμος δημοσίευσης', termsOrComment: 'Όροι ή σχόλιο', reviewDraft: 'Ελέγξτε και επεξεργαστείτε το προσχέδιο', publicationDate: 'Ημερομηνία δημοσίευσης', assignTask: 'Τι να αναθέσετε', expectedResult: 'Αναμενόμενο αποτέλεσμα', defaultExpectedResult: 'Υλικά έτοιμα για έλεγχο', runInstructions: 'Ρυθμίστε και εκτελέστε τον βοηθό AI στον χώρο εργασίας παρακάτω. Έπειτα επιστρέψτε σε αυτό το βήμα και επιλέξτε «Έλεγχος ολοκληρωμένης εκτέλεσης».', confirmedResult: 'Τι επιβεβαίωσε το αποτέλεσμα εκτέλεσης', inquiries: 'Ερωτήματα', sales: 'Πωλήσεις', views: 'Προβολές', copy: 'Αντιγραφή', noReplyFollowup: 'Χωρίς απάντηση — προετοιμασία υπενθύμισης',
    commands: { mark_sent: 'Το μήνυμα σημειώθηκε ως σταλμένο', record_reply: 'Αποθήκευση απάντησης', prepare_followup: 'Προετοιμασία υπενθύμισης', save_terms: 'Αποθήκευση όρων', mark_launched: 'Η συνεργασία σημειώθηκε ως ξεκίνησε', mark_published: 'Η δημοσίευση σημειώθηκε ως δημοσιευμένη', add_result: 'Προσθήκη αποτελέσματος', complete: 'Έτοιμο', start_next_cycle: 'Έναρξη επόμενου κύκλου', open_upgrade: 'Επιλογή προγράμματος', prepare: 'Προετοιμασία προσχεδίου', save_draft: 'Αποθήκευση προσχεδίου', schedule: 'Προσθήκη στο ημερολόγιο', refresh: 'Ανανέωση δεδομένων', retry_refresh: 'Επανάληψη ανανέωσης', save_configuration: 'Αποθήκευση ρύθμισης', approve: 'Επιβεβαίωση πλάνου', link_run: 'Έλεγχος ολοκληρωμένης εκτέλεσης' },
    outcomes: { interested: 'Ενδιαφέρεται', paid: 'Ζητά πληρωμή', barter: 'Ανοιχτός σε ανταλλαγή', details: 'Χρειάζονται λεπτομέρειες', refused: 'Αρνήθηκε', other: 'Άλλο' },
    useCases: { reviews_without_reply: 'Συλλογή κριτικών χωρίς απάντηση', content_drafts: 'Προετοιμασία προσχεδίων περιεχομένου', map_changes: 'Έλεγχος αλλαγών καταχώρισης', weekly_summary: 'Προετοιμασία εβδομαδιαίας σύνοψης' },
  },
  de: {
    now: 'Was jetzt zu tun ist', due: 'Fällig am', replyOutcomeLabel: 'Antwortergebnis', saveError: 'Die Aktion konnte nicht gespeichert werden', publicationUrl: 'Link zur Veröffentlichung', termsOrComment: 'Bedingungen oder Kommentar', reviewDraft: 'Entwurf prüfen und bearbeiten', publicationDate: 'Veröffentlichungsdatum', assignTask: 'Aufgabe festlegen', expectedResult: 'Erwartetes Ergebnis', defaultExpectedResult: 'Unterlagen zur Prüfung vorbereitet', runInstructions: 'Richten Sie den KI-Assistenten im Arbeitsbereich unten ein und starten Sie ihn. Kehren Sie dann zu diesem Schritt zurück und wählen Sie „Abgeschlossenen Lauf prüfen“.', confirmedResult: 'Was das Laufergebnis bestätigt hat', inquiries: 'Anfragen', sales: 'Verkäufe', views: 'Aufrufe', copy: 'Kopieren', noReplyFollowup: 'Keine Antwort — Follow-up vorbereiten',
    commands: { mark_sent: 'Nachricht als gesendet markiert', record_reply: 'Antwort speichern', prepare_followup: 'Follow-up vorbereiten', save_terms: 'Bedingungen speichern', mark_launched: 'Partnerschaft als gestartet markiert', mark_published: 'Veröffentlichung als erschienen markiert', add_result: 'Ergebnis hinzufügen', complete: 'Fertig', start_next_cycle: 'Nächsten Zyklus starten', open_upgrade: 'Tarif wählen', prepare: 'Entwurf vorbereiten', save_draft: 'Entwurf speichern', schedule: 'Zum Kalender hinzufügen', refresh: 'Daten aktualisieren', retry_refresh: 'Aktualisierung wiederholen', save_configuration: 'Einrichtung speichern', approve: 'Plan bestätigen', link_run: 'Abgeschlossenen Lauf prüfen' },
    outcomes: { interested: 'Interessiert', paid: 'Bittet um Zahlung', barter: 'Offen für Tausch', details: 'Benötigt Details', refused: 'Abgelehnt', other: 'Andere' },
    useCases: { reviews_without_reply: 'Bewertungen ohne Antwort sammeln', content_drafts: 'Inhaltsentwürfe vorbereiten', map_changes: 'Änderungen am Eintrag prüfen', weekly_summary: 'Wöchentliche Zusammenfassung vorbereiten' },
  },
  th: {
    now: 'สิ่งที่ต้องทำตอนนี้', due: 'กำหนดส่ง', replyOutcomeLabel: 'ผลลัพธ์ของการตอบกลับ', saveError: 'ไม่สามารถบันทึกการดำเนินการได้', publicationUrl: 'ลิงก์เผยแพร่', termsOrComment: 'เงื่อนไขหรือความคิดเห็น', reviewDraft: 'ตรวจสอบและแก้ไขฉบับร่าง', publicationDate: 'วันที่เผยแพร่', assignTask: 'มอบหมายงาน', expectedResult: 'ผลลัพธ์ที่คาดหวัง', defaultExpectedResult: 'เตรียมเอกสารสำหรับตรวจสอบแล้ว', runInstructions: 'ตั้งค่าและเริ่มผู้ช่วย AI ในพื้นที่ทำงานด้านล่าง จากนั้นกลับมาที่ขั้นตอนนี้และเลือก «ตรวจสอบการทำงานที่เสร็จสิ้น».', confirmedResult: 'สิ่งที่ผลการทำงานยืนยัน', inquiries: 'คำถาม', sales: 'ยอดขาย', views: 'การดู', copy: 'คัดลอก', noReplyFollowup: 'ไม่มีการตอบกลับ — เตรียมติดตามผล',
    commands: { mark_sent: 'ทำเครื่องหมายว่าส่งข้อความแล้ว', record_reply: 'บันทึกคำตอบ', prepare_followup: 'เตรียมติดตามผล', save_terms: 'บันทึกเงื่อนไข', mark_launched: 'ทำเครื่องหมายว่าเริ่มความร่วมมือแล้ว', mark_published: 'ทำเครื่องหมายว่าเผยแพร่แล้ว', add_result: 'เพิ่มผลลัพธ์', complete: 'เสร็จสิ้น', start_next_cycle: 'เริ่มรอบถัดไป', open_upgrade: 'เลือกแพ็กเกจ', prepare: 'เตรียมฉบับร่าง', save_draft: 'บันทึกฉบับร่าง', schedule: 'เพิ่มในปฏิทิน', refresh: 'อัปเดตข้อมูล', retry_refresh: 'ลองอัปเดตอีกครั้ง', save_configuration: 'บันทึกการตั้งค่า', approve: 'ยืนยันแผน', link_run: 'ตรวจสอบการทำงานที่เสร็จสิ้น' },
    outcomes: { interested: 'สนใจ', paid: 'ขอชำระเงิน', barter: 'เปิดรับการแลกเปลี่ยน', details: 'ต้องการรายละเอียด', refused: 'ปฏิเสธ', other: 'อื่น ๆ' },
    useCases: { reviews_without_reply: 'รวบรวมรีวิวที่ยังไม่ตอบ', content_drafts: 'เตรียมร่างเนื้อหา', map_changes: 'ตรวจสอบการเปลี่ยนแปลงข้อมูลธุรกิจ', weekly_summary: 'เตรียมสรุปรายสัปดาห์' },
  },
  ar: {
    now: 'ما الذي يجب فعله الآن', due: 'الموعد النهائي', replyOutcomeLabel: 'نتيجة الرد', saveError: 'تعذر حفظ الإجراء', publicationUrl: 'رابط النشر', termsOrComment: 'الشروط أو تعليق', reviewDraft: 'راجع المسودة وعدّلها', publicationDate: 'تاريخ النشر', assignTask: 'ما الذي تريد تكليفه', expectedResult: 'النتيجة المتوقعة', defaultExpectedResult: 'مواد جاهزة للمراجعة', runInstructions: 'أعِد وشغّل مساعد الذكاء الاصطناعي في مساحة العمل أدناه. ثم عُد إلى هذه الخطوة واختر «التحقق من التشغيل المكتمل».', confirmedResult: 'ما أكده ناتج التشغيل', inquiries: 'استفسارات', sales: 'مبيعات', views: 'مشاهدات', copy: 'نسخ', noReplyFollowup: 'لا رد — إعداد متابعة',
    commands: { mark_sent: 'تم وضع علامة على الرسالة كمرسلة', record_reply: 'حفظ الرد', prepare_followup: 'إعداد متابعة', save_terms: 'حفظ الشروط', mark_launched: 'تم وضع علامة على الشراكة كبادئة', mark_published: 'تم وضع علامة على النشر كمنشور', add_result: 'إضافة نتيجة', complete: 'تم', start_next_cycle: 'بدء الدورة التالية', open_upgrade: 'اختيار الخطة', prepare: 'إعداد مسودة', save_draft: 'حفظ المسودة', schedule: 'إضافة إلى التقويم', refresh: 'تحديث البيانات', retry_refresh: 'إعادة محاولة التحديث', save_configuration: 'حفظ الإعداد', approve: 'تأكيد الخطة', link_run: 'التحقق من التشغيل المكتمل' },
    outcomes: { interested: 'مهتم', paid: 'يطلب الدفع', barter: 'منفتح على المقايضة', details: 'يحتاج إلى تفاصيل', refused: 'رفض', other: 'أخرى' },
    useCases: { reviews_without_reply: 'جمع المراجعات بلا رد', content_drafts: 'إعداد مسودات المحتوى', map_changes: 'التحقق من تغييرات الملف التجاري', weekly_summary: 'إعداد ملخص أسبوعي' },
  },
  ha: {
    now: 'Abin da za a yi yanzu', due: 'Ranar ƙarshe', replyOutcomeLabel: 'Sakamakon amsa', saveError: 'Ba a iya ajiye aikin ba', publicationUrl: 'Hanyar zuwa wallafar', termsOrComment: 'Sharuɗɗa ko bayani', reviewDraft: 'Duba kuma gyara daftarin', publicationDate: 'Ranar wallafawa', assignTask: 'Abin da za a ba wa aiki', expectedResult: 'Sakamakon da ake tsammani', defaultExpectedResult: 'An shirya kayan don dubawa', runInstructions: 'Saita kuma kunna mataimakin AI a wurin aiki da ke ƙasa. Sa’an nan ku dawo wannan matakin ku zaɓi «Duba aikin da aka kammala».', confirmedResult: 'Abin da sakamakon aikin ya tabbatar', inquiries: 'Tambayoyi', sales: 'Tallace-tallace', views: 'Kallo', copy: 'Kwafi', noReplyFollowup: 'Babu amsa — shirya bibiyar baya',
    commands: { mark_sent: 'An yi wa saƙo alamar an aika', record_reply: 'Ajiye amsa', prepare_followup: 'Shirya bibiyar baya', save_terms: 'Ajiye sharuɗɗa', mark_launched: 'An yi wa haɗin gwiwa alamar an fara', mark_published: 'An yi wa wallafa alamar ta fito', add_result: 'Ƙara sakamako', complete: 'An gama', start_next_cycle: 'Fara zagaye na gaba', open_upgrade: 'Zaɓi tsari', prepare: 'Shirya daftari', save_draft: 'Ajiye daftari', schedule: 'Ƙara zuwa kalanda', refresh: 'Sabunta bayanai', retry_refresh: 'Sake gwada sabuntawa', save_configuration: 'Ajiye saiti', approve: 'Tabbatar da shiri', link_run: 'Duba aikin da aka kammala' },
    outcomes: { interested: 'Yana sha’awa', paid: 'Yana neman biyan kuɗi', barter: 'A buɗe yake ga musayar kaya', details: 'Ana buƙatar ƙarin bayani', refused: 'Ya ƙi', other: 'Wani' },
    useCases: { reviews_without_reply: 'Tattara ra’ayoyin da ba a ba da amsa ba', content_drafts: 'Shirya daftarin abun ciki', map_changes: 'Duba canje-canje a katin kasuwanci', weekly_summary: 'Shirya taƙaitaccen mako-mako' },
  },
  tr: {
    now: 'Şimdi ne yapılmalı', due: 'Son tarih', replyOutcomeLabel: 'Yanıt sonucu', saveError: 'İşlem kaydedilemedi', publicationUrl: 'Yayın bağlantısı', termsOrComment: 'Koşullar veya yorum', reviewDraft: 'Taslağı gözden geçirin ve düzenleyin', publicationDate: 'Yayın tarihi', assignTask: 'Ne görevlendirilsin', expectedResult: 'Beklenen sonuç', defaultExpectedResult: 'İnceleme için hazırlanmış materyaller', runInstructions: 'Aşağıdaki çalışma alanında yapay zekâ asistanını kurun ve çalıştırın. Ardından bu adıma dönüp «Tamamlanan çalıştırmayı kontrol et» seçeneğini seçin.', confirmedResult: 'Çalıştırma sonucunun doğruladıkları', inquiries: 'Talepler', sales: 'Satışlar', views: 'Görüntülemeler', copy: 'Kopyala', noReplyFollowup: 'Yanıt yok — takip hazırlayın',
    commands: { mark_sent: 'Mesaj gönderildi olarak işaretlendi', record_reply: 'Yanıtı kaydet', prepare_followup: 'Takip hazırla', save_terms: 'Koşulları kaydet', mark_launched: 'Ortaklık başlatıldı olarak işaretlendi', mark_published: 'Yayın yayımlandı olarak işaretlendi', add_result: 'Sonuç ekle', complete: 'Tamam', start_next_cycle: 'Sonraki döngüyü başlat', open_upgrade: 'Plan seç', prepare: 'Taslak hazırla', save_draft: 'Taslağı kaydet', schedule: 'Takvime ekle', refresh: 'Verileri güncelle', retry_refresh: 'Güncellemeyi yeniden dene', save_configuration: 'Kurulumu kaydet', approve: 'Planı onayla', link_run: 'Tamamlanan çalıştırmayı kontrol et' },
    outcomes: { interested: 'İlgileniyor', paid: 'Ödeme istiyor', barter: 'Takasla ilgileniyor', details: 'Ayrıntı gerekiyor', refused: 'Reddetti', other: 'Diğer' },
    useCases: { reviews_without_reply: 'Yanıtsız yorumları topla', content_drafts: 'İçerik taslakları hazırla', map_changes: 'İşletme kartı değişikliklerini kontrol et', weekly_summary: 'Haftalık özet hazırla' },
  },
};

export const journeyActionCopy = (language: Language): JourneyActionCopy => copy[language];
