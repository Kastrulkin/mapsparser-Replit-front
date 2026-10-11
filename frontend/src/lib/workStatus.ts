import type { Language } from '@/i18n/LanguageContext.logic';
export type WorkStatus = 'not_started' | 'planned' | 'running' | 'decision' | 'blocked' | 'error' | 'completed' | 'unknown';
export const workStatus = (status?: string | null): WorkStatus => {
 if (['new','imported','not_started'].includes(status || '')) return 'not_started';
 if (['pending','queued','scheduled','planned','provider_request_queued'].includes(status || '')) return 'planned';
 if (['running','processing','in_progress','waiting_provider','provider_executing','sent','delivered','waiting'].includes(status || '')) return 'running';
 if (['ready','approved','approved_for_send','draft','draft_generated','edited','needs_review','waiting_approval','awaiting_approval','approval_required','replied','negotiating'].includes(status || '')) return 'decision';
 if (['blocked','provider_unavailable','approval_invalid','disputed','provider_reconciliation_required'].includes(status || '')) return 'blocked';
 if (['failed','provider_failed','error'].includes(status || '')) return 'error';
 if (['completed','published','succeeded'].includes(status || '')) return 'completed';
 return 'unknown';
};
const keys: WorkStatus[] = ['not_started','planned','running','decision','blocked','error','completed','unknown'];
const labels: Record<Language, string[]> = {
 ru: ['Не начато','Запланировано','Выполняется','Нужно решение','Заблокировано','Ошибка','Завершено','Статус не уточнён'],
 en: ['Not started','Planned','Running','Needs a decision','Blocked','Error','Completed','Status not specified'],
 fr: ['Non commencé','Planifié','En cours','Décision requise','Bloqué','Erreur','Terminé','Statut non précisé'],
 es: ['Sin iniciar','Planificado','En curso','Requiere decisión','Bloqueado','Error','Completado','Estado no indicado'],
 el: ['Δεν ξεκίνησε','Προγραμματισμένο','Σε εξέλιξη','Απαιτείται απόφαση','Μπλοκαρισμένο','Σφάλμα','Ολοκληρώθηκε','Άγνωστη κατάσταση'],
 de: ['Nicht begonnen','Geplant','In Arbeit','Entscheidung erforderlich','Blockiert','Fehler','Abgeschlossen','Status nicht angegeben'],
 th: ['ยังไม่เริ่ม','วางแผนแล้ว','กำลังทำงาน','ต้องตัดสินใจ','ถูกบล็อก','ข้อผิดพลาด','เสร็จแล้ว','ไม่ระบุสถานะ'],
 ar: ['لم يبدأ','مخطط','قيد التنفيذ','يحتاج قراراً','محظور','خطأ','مكتمل','الحالة غير محددة'],
 ha: ['Ba a fara ba','An shirya','Ana aiki','Ana buƙatar shawara','An toshe','Kuskure','An kammala','Ba a bayyana matsayi ba'],
 tr: ['Başlamadı','Planlandı','Çalışıyor','Karar gerekiyor','Engellendi','Hata','Tamamlandı','Durum belirtilmedi'],
 hy: ['Չի սկսվել','Պլանավորված','Ընթացքի մեջ','Որոշում է պետք','Արգելափակված','Սխալ','Ավարտված','Կարգավիճակը նշված չէ'],
};
export const workStatusLabel = (status: string | undefined | null, language: Language) => labels[language][keys.indexOf(workStatus(status))];

const details: Record<Language, string[]> = {
 ru: ['Черновик подготовлен','Одобрено к отправке','В очереди','Отправка подтверждена','Доставка подтверждена','Публикация подтверждена'],
 en: ['Draft prepared','Approved for sending','Queued','Sending confirmed','Delivery confirmed','Publication confirmed'],
 fr: ['Brouillon préparé','Envoi approuvé','En attente','Envoi confirmé','Livraison confirmée','Publication confirmée'],
 es: ['Borrador preparado','Envío aprobado','En cola','Envío confirmado','Entrega confirmada','Publicación confirmada'],
 el: ['Προσχέδιο έτοιμο','Εγκρίθηκε η αποστολή','Στην ουρά','Επιβεβαιώθηκε η αποστολή','Επιβεβαιώθηκε η παράδοση','Επιβεβαιώθηκε η δημοσίευση'],
 de: ['Entwurf vorbereitet','Versand genehmigt','In Warteschlange','Versand bestätigt','Zustellung bestätigt','Veröffentlichung bestätigt'],
 th: ['เตรียมร่างแล้ว','อนุมัติให้ส่ง','อยู่ในคิว','ยืนยันการส่ง','ยืนยันการจัดส่ง','ยืนยันการเผยแพร่'],
 ar: ['مسودة جاهزة','موافق على الإرسال','في الانتظار','الإرسال مؤكد','التسليم مؤكد','النشر مؤكد'],
 ha: ['An shirya daftari','An amince da aikawa','A jerin jira','An tabbatar da aikawa','An tabbatar da isarwa','An tabbatar da wallafawa'],
 tr: ['Taslak hazır','Gönderim onaylandı','Kuyrukta','Gönderim doğrulandı','Teslimat doğrulandı','Yayın doğrulandı'],
 hy: ['Սևագիրը պատրաստ է','Ուղարկումը հաստատված է','Հերթում է','Ուղարկումը ստուգված է','Առաքումը ստուգված է','Հրապարակումը ստուգված է'],
};
export const workStatusDetail = (status: string | null | undefined, language: Language) => {
 const index = status === 'draft' || status === 'draft_generated' ? 0 : status === 'approved_for_send' ? 1 : status === 'queued' || status === 'provider_request_queued' ? 2 : status === 'sent' ? 3 : status === 'delivered' ? 4 : status === 'published' ? 5 : -1;
 return index >= 0 ? details[language][index] : workStatusLabel(status, language);
};
