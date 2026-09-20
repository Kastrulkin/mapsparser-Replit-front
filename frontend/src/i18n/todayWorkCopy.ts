import type { Language } from './LanguageContext.logic';

type WorkCopy = {
  open: string;
  waiting: string;
  executing: string;
  reconciliation: string;
  failed: string;
  unavailable: string;
  invalidApproval: string;
};

// Only explicit API-owned display codes are translated. Titles, drafts, and
// unknown/legacy messages are not translation keys, even when their text matches.
const copy: Record<Language, WorkCopy> = {
  ru: {
    open: 'Открыть',
    waiting: 'Запись в таблицу подтверждена и ожидает выполнения.',
    executing: 'Выполняется запись в таблицу.',
    reconciliation: 'Результат записи неизвестен. Сверьте таблицу перед следующими действиями.',
    failed: 'Запись требует внимания. Откройте результат, чтобы проверить причину.',
    unavailable: 'Для записи нужен доступ к таблице. Откройте результат, чтобы проверить подключение.',
    invalidApproval: 'Подтверждение записи больше не действует. Откройте результат для проверки.',
  },
  en: {
    open: 'Open',
    waiting: 'The spreadsheet write is approved and waiting to run.',
    executing: 'Writing to the spreadsheet.',
    reconciliation: 'The write outcome is unknown. Check the spreadsheet before taking further action.',
    failed: 'The write needs attention. Open the result to check the cause.',
    unavailable: 'Spreadsheet access is required for the write. Open the result to check the connection.',
    invalidApproval: 'The write approval is no longer valid. Open the result to review it.',
  },
  es: {
    open: 'Abrir',
    waiting: 'La escritura en la hoja está aprobada y pendiente de ejecución.',
    executing: 'Se está escribiendo en la hoja.',
    reconciliation: 'Se desconoce el resultado de la escritura. Revisa la hoja antes de continuar.',
    failed: 'La escritura requiere atención. Abre el resultado para comprobar la causa.',
    unavailable: 'Se necesita acceso a la hoja para escribir. Abre el resultado para comprobar la conexión.',
    invalidApproval: 'La aprobación de la escritura ya no es válida. Abre el resultado para revisarlo.',
  },
  fr: {
    open: 'Ouvrir',
    waiting: 'L’écriture dans la feuille est approuvée et en attente d’exécution.',
    executing: 'Écriture dans la feuille en cours.',
    reconciliation: 'Le résultat de l’écriture est inconnu. Vérifiez la feuille avant de poursuivre.',
    failed: 'L’écriture nécessite votre attention. Ouvrez le résultat pour vérifier la cause.',
    unavailable: 'Un accès à la feuille est nécessaire pour écrire. Ouvrez le résultat pour vérifier la connexion.',
    invalidApproval: 'L’approbation de l’écriture n’est plus valide. Ouvrez le résultat pour le vérifier.',
  },
  de: {
    open: 'Öffnen',
    waiting: 'Der Schreibvorgang in die Tabelle ist freigegeben und wartet auf die Ausführung.',
    executing: 'Daten werden in die Tabelle geschrieben.',
    reconciliation: 'Das Ergebnis des Schreibvorgangs ist unbekannt. Prüfen Sie die Tabelle, bevor Sie fortfahren.',
    failed: 'Der Schreibvorgang erfordert Aufmerksamkeit. Öffnen Sie das Ergebnis, um die Ursache zu prüfen.',
    unavailable: 'Für den Schreibvorgang ist Tabellenzugriff erforderlich. Öffnen Sie das Ergebnis, um die Verbindung zu prüfen.',
    invalidApproval: 'Die Freigabe des Schreibvorgangs ist nicht mehr gültig. Öffnen Sie das Ergebnis zur Prüfung.',
  },
  el: {
    open: 'Άνοιγμα',
    waiting: 'Η εγγραφή στο φύλλο έχει εγκριθεί και αναμένει εκτέλεση.',
    executing: 'Η εγγραφή στο φύλλο βρίσκεται σε εξέλιξη.',
    reconciliation: 'Το αποτέλεσμα της εγγραφής είναι άγνωστο. Ελέγξτε το φύλλο πριν συνεχίσετε.',
    failed: 'Η εγγραφή χρειάζεται προσοχή. Ανοίξτε το αποτέλεσμα για να ελέγξετε την αιτία.',
    unavailable: 'Απαιτείται πρόσβαση στο φύλλο για την εγγραφή. Ανοίξτε το αποτέλεσμα για να ελέγξετε τη σύνδεση.',
    invalidApproval: 'Η έγκριση της εγγραφής δεν ισχύει πλέον. Ανοίξτε το αποτέλεσμα για έλεγχο.',
  },
  tr: {
    open: 'Aç',
    waiting: 'Tabloya yazma işlemi onaylandı ve yürütülmeyi bekliyor.',
    executing: 'Tabloya yazılıyor.',
    reconciliation: 'Yazma işleminin sonucu bilinmiyor. Devam etmeden önce tabloyu kontrol edin.',
    failed: 'Yazma işlemi dikkat gerektiriyor. Nedeni kontrol etmek için sonucu açın.',
    unavailable: 'Yazma işlemi için tabloya erişim gerekiyor. Bağlantıyı kontrol etmek için sonucu açın.',
    invalidApproval: 'Yazma onayı artık geçerli değil. İncelemek için sonucu açın.',
  },
  th: {
    open: 'เปิด',
    waiting: 'การเขียนลงตารางได้รับการอนุมัติแล้วและกำลังรอดำเนินการ',
    executing: 'กำลังเขียนลงตาราง',
    reconciliation: 'ยังไม่ทราบผลการเขียน โปรดตรวจสอบตารางก่อนดำเนินการต่อ',
    failed: 'การเขียนต้องได้รับการตรวจสอบ เปิดผลลัพธ์เพื่อตรวจสอบสาเหตุ',
    unavailable: 'ต้องมีสิทธิ์เข้าถึงตารางจึงจะเขียนได้ เปิดผลลัพธ์เพื่อตรวจสอบการเชื่อมต่อ',
    invalidApproval: 'การอนุมัติการเขียนใช้ไม่ได้แล้ว เปิดผลลัพธ์เพื่อตรวจสอบ',
  },
  ar: {
    open: 'فتح',
    waiting: 'تمت الموافقة على الكتابة في الجدول وهي بانتظار التنفيذ.',
    executing: 'جارٍ الكتابة في الجدول.',
    reconciliation: 'نتيجة الكتابة غير معروفة. تحقق من الجدول قبل المتابعة.',
    failed: 'الكتابة تحتاج إلى مراجعة. افتح النتيجة للتحقق من السبب.',
    unavailable: 'الكتابة تتطلب الوصول إلى الجدول. افتح النتيجة للتحقق من الاتصال.',
    invalidApproval: 'لم تعد الموافقة على الكتابة صالحة. افتح النتيجة لمراجعتها.',
  },
  ha: {
    open: 'Buɗe',
    waiting: 'An amince da rubutu a takardar lissafi kuma yana jiran aiwatarwa.',
    executing: 'Ana rubutu a takardar lissafi.',
    reconciliation: 'Ba a san sakamakon rubutun ba. Duba takardar lissafi kafin ci gaba.',
    failed: 'Rubutun yana buƙatar kulawa. Buɗe sakamakon don duba dalili.',
    unavailable: 'Ana buƙatar damar shiga takardar lissafi don rubutu. Buɗe sakamakon don duba haɗin.',
    invalidApproval: 'Amincewar rubutun ba ta da inganci kuma. Buɗe sakamakon don dubawa.',
  },
};

const descriptionKeys = new Map<string, keyof Omit<WorkCopy, 'open'>>([
  ['today.automation.waiting_provider', 'waiting'],
  ['today.automation.provider_request_queued', 'waiting'],
  ['today.automation.provider_executing', 'executing'],
  ['today.automation.provider_reconciliation_required', 'reconciliation'],
  ['today.automation.provider_failed', 'failed'],
  ['today.automation.provider_unavailable', 'unavailable'],
  ['today.automation.approval_invalid', 'invalidApproval'],
]);

export const todayWorkDescription = (language: Language, code: string | undefined, fallback: string) => {
  const key = descriptionKeys.get(code || '');
  return key ? copy[language][key] : fallback;
};

export const todayWorkActionLabel = (language: Language, code: string | undefined, fallback: string) => (
  code === 'today.open' ? copy[language].open : fallback
);
