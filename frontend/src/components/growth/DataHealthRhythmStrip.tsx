import { ArrowRight, CheckCircle2, Clock3, DatabaseZap, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useLanguage, type Language } from '@/i18n/LanguageContext';
import { cn } from '@/lib/utils';

export type GrowthDataHealth = {
  status?: string;
  state?: string;
  freshness?: string;
  source?: string;
  source_label?: string;
  source_updated_at?: string | null;
  updated_at?: string | null;
  last_updated_at?: string | null;
  age_days?: number | null;
  record_count?: number;
  next_due_at?: string | null;
  missing?: string[];
  reason?: string;
  is_stale?: boolean;
  stale?: boolean;
};

type DataHealthRhythmStripProps = {
  dataHealth?: GrowthDataHealth | null;
  onImport: () => void;
  compact?: boolean;
  showImportAction?: boolean;
};

type DataHealthCopy = {
  aria: string;
  needsUpdate: string;
  ready: string;
  source: string;
  missing: string;
  stale: string;
  current: string;
  upload: string;
  manual: string;
  calculated: string;
  file: string;
  unknown: string;
};

const dataHealthCopy: Record<Language, DataHealthCopy> = {
  ru: { aria: 'Свежесть данных и ритм анализа', needsUpdate: 'Данные требуют обновления', ready: 'Данные готовы к анализу', source: 'Источник', missing: 'Для полного отчёта добавьте недостающие данные.', stale: 'Загрузите свежую выгрузку, чтобы открыть актуальную аналитику.', current: 'Показатели обновляются из подтверждённого источника. Следующий шаг — проверить выводы за период.', upload: 'Загрузить файл из CRM', manual: 'ввод вручную', calculated: 'расчёт LocalOS', file: 'загруженный файл', unknown: 'не указан' },
  en: { aria: 'Data freshness and analysis rhythm', needsUpdate: 'Data needs updating', ready: 'Data is ready for analysis', source: 'Source', missing: 'Add the missing data to complete the report.', stale: 'Upload a fresh export to open up-to-date analytics.', current: 'Metrics are updated from a verified source. Next, review the findings for the period.', upload: 'Upload a file from your CRM', manual: 'manual entry', calculated: 'LocalOS calculation', file: 'uploaded file', unknown: 'not specified' },
  fr: { aria: 'Fraîcheur des données et rythme d’analyse', needsUpdate: 'Les données doivent être actualisées', ready: 'Les données sont prêtes pour l’analyse', source: 'Source', missing: 'Ajoutez les données manquantes pour compléter le rapport.', stale: 'Importez un export récent pour afficher l’analyse à jour.', current: 'Les indicateurs proviennent d’une source vérifiée. Vérifiez ensuite les conclusions de la période.', upload: 'Importer un fichier depuis votre CRM', manual: 'saisie manuelle', calculated: 'calcul LocalOS', file: 'fichier importé', unknown: 'non indiqué' },
  es: { aria: 'Actualidad de los datos y ritmo de análisis', needsUpdate: 'Los datos deben actualizarse', ready: 'Los datos están listos para analizar', source: 'Fuente', missing: 'Añade los datos que faltan para completar el informe.', stale: 'Carga una exportación reciente para abrir el análisis actualizado.', current: 'Los indicadores proceden de una fuente verificada. Después, revisa las conclusiones del periodo.', upload: 'Cargar un archivo desde tu CRM', manual: 'entrada manual', calculated: 'cálculo de LocalOS', file: 'archivo cargado', unknown: 'sin especificar' },
  el: { aria: 'Ενημέρωση δεδομένων και ρυθμός ανάλυσης', needsUpdate: 'Τα δεδομένα χρειάζονται ενημέρωση', ready: 'Τα δεδομένα είναι έτοιμα για ανάλυση', source: 'Πηγή', missing: 'Προσθέστε τα δεδομένα που λείπουν για να ολοκληρωθεί η αναφορά.', stale: 'Ανεβάστε μια πρόσφατη εξαγωγή για ενημερωμένα αναλυτικά στοιχεία.', current: 'Οι δείκτες ενημερώνονται από επαληθευμένη πηγή. Στη συνέχεια, ελέγξτε τα συμπεράσματα της περιόδου.', upload: 'Ανεβάστε αρχείο από το CRM', manual: 'χειροκίνητη εισαγωγή', calculated: 'υπολογισμός LocalOS', file: 'ανεβασμένο αρχείο', unknown: 'δεν καθορίστηκε' },
  de: { aria: 'Datenaktualität und Analyserhythmus', needsUpdate: 'Daten müssen aktualisiert werden', ready: 'Daten sind analysebereit', source: 'Quelle', missing: 'Ergänzen Sie die fehlenden Daten für den vollständigen Bericht.', stale: 'Laden Sie einen aktuellen Export für eine aktuelle Analyse hoch.', current: 'Die Kennzahlen stammen aus einer bestätigten Quelle. Prüfen Sie anschließend die Ergebnisse des Zeitraums.', upload: 'Datei aus dem CRM hochladen', manual: 'manuelle Eingabe', calculated: 'LocalOS-Berechnung', file: 'hochgeladene Datei', unknown: 'nicht angegeben' },
  th: { aria: 'ความใหม่ของข้อมูลและรอบการวิเคราะห์', needsUpdate: 'ข้อมูลต้องอัปเดต', ready: 'ข้อมูลพร้อมสำหรับการวิเคราะห์', source: 'แหล่งที่มา', missing: 'เพิ่มข้อมูลที่ขาดเพื่อให้รายงานสมบูรณ์', stale: 'อัปโหลดไฟล์ส่งออกล่าสุดเพื่อดูการวิเคราะห์ที่เป็นปัจจุบัน', current: 'ตัวชี้วัดอัปเดตจากแหล่งข้อมูลที่ยืนยันแล้ว ขั้นต่อไปคือตรวจสอบข้อสรุปของช่วงเวลา', upload: 'อัปโหลดไฟล์จาก CRM', manual: 'กรอกด้วยตนเอง', calculated: 'การคำนวณของ LocalOS', file: 'ไฟล์ที่อัปโหลด', unknown: 'ไม่ได้ระบุ' },
  ar: { aria: 'حداثة البيانات وإيقاع التحليل', needsUpdate: 'تحتاج البيانات إلى تحديث', ready: 'البيانات جاهزة للتحليل', source: 'المصدر', missing: 'أضف البيانات الناقصة لإكمال التقرير.', stale: 'حمّل تصديراً حديثاً لعرض التحليلات المحدثة.', current: 'تُحدّث المؤشرات من مصدر موثّق. الخطوة التالية هي مراجعة نتائج الفترة.', upload: 'تحميل ملف من نظام CRM', manual: 'إدخال يدوي', calculated: 'حساب LocalOS', file: 'ملف محمّل', unknown: 'غير محدد' },
  ha: { aria: 'Sabuntar bayanai da tsarin nazari', needsUpdate: 'Ana buƙatar sabunta bayanai', ready: 'Bayanai sun shirya don nazari', source: 'Tushe', missing: 'Ƙara bayanan da suka rage domin kammala rahoton.', stale: 'Loda sabon fayil domin buɗe nazari na yanzu.', current: 'Ana sabunta ma’aunai daga tushe da aka tabbatar. Sai a duba sakamakon wannan lokacin.', upload: 'Loda fayil daga CRM', manual: 'shigarwa da hannu', calculated: 'lissafin LocalOS', file: 'fayil da aka loda', unknown: 'ba a bayyana ba' },
  tr: { aria: 'Veri güncelliği ve analiz ritmi', needsUpdate: 'Verilerin güncellenmesi gerekiyor', ready: 'Veriler analize hazır', source: 'Kaynak', missing: 'Raporu tamamlamak için eksik verileri ekleyin.', stale: 'Güncel analizleri açmak için yeni bir dışa aktarma dosyası yükleyin.', current: 'Göstergeler doğrulanmış bir kaynaktan güncellenir. Sonraki adım dönem sonuçlarını incelemektir.', upload: 'CRM’den dosya yükle', manual: 'manuel giriş', calculated: 'LocalOS hesaplaması', file: 'yüklenen dosya', unknown: 'belirtilmedi' },
};

const dateLocales: Record<Language, string> = { ru: 'ru-RU', en: 'en-GB', fr: 'fr-FR', es: 'es-ES', el: 'el-GR', de: 'de-DE', th: 'th-TH', ar: 'ar', ha: 'ha-NG', tr: 'tr-TR' };

const dateLabel = (value: string | null | undefined, locale: string) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(date);
};

const sourceLabel = (value: string | undefined, copy: DataHealthCopy) => {
  const normalized = `${value || ''}`.trim().toLowerCase();
  if (!normalized || normalized === 'unknown' || normalized === 'n/a' || normalized === 'none') return copy.unknown;
  if (normalized.includes('yclients')) return 'YCLIENTS';
  if (normalized.includes('altegio')) return 'Altegio';
  if (normalized === 'manual') return copy.manual;
  if (normalized === 'calculated') return copy.calculated;
  if (normalized === 'import' || normalized === 'file') return copy.file;
  return value || copy.unknown;
};

const needsImport = (dataHealth: GrowthDataHealth) => {
  const state = `${dataHealth.status || ''} ${dataHealth.state || ''} ${dataHealth.freshness || ''}`.toLowerCase();
  return Boolean(dataHealth.stale || dataHealth.is_stale || dataHealth.missing?.length || /missing|stale|empty|unavailable|attention/.test(state));
};

export const DataHealthRhythmStrip = ({ dataHealth, onImport, compact = false, showImportAction = true }: DataHealthRhythmStripProps) => {
  const { language } = useLanguage();
  if (!dataHealth) return null;
  const copy = dataHealthCopy[language];
  const importNeeded = needsImport(dataHealth);
  const updatedAt = dateLabel(dataHealth.source_updated_at || dataHealth.updated_at || dataHealth.last_updated_at, dateLocales[language]);
  const source = sourceLabel(language === 'ru' && dataHealth.source_label ? dataHealth.source_label : dataHealth.source, copy);
  const missing = dataHealth.missing?.filter(Boolean) || [];
  const Icon = importNeeded ? TriangleAlert : CheckCircle2;

  return (
    <section className={cn(
      'flex flex-col gap-3 rounded-2xl bg-slate-50 px-4 py-3 shadow-[0_0_0_1px_rgba(15,23,42,0.08)] sm:flex-row sm:items-center sm:justify-between',
      compact ? 'text-sm' : 'text-sm',
    )} aria-label={copy.aria}>
      <div className="flex min-w-0 items-start gap-3">
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl', importNeeded ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700')}>
          <Icon className="h-5 w-5" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="font-semibold text-slate-950">{importNeeded ? copy.needsUpdate : copy.ready}</span>
            <span className="inline-flex items-center gap-1 text-xs text-slate-500"><DatabaseZap className="h-3.5 w-3.5" />{copy.source}: {source}</span>
            {updatedAt ? <span className="inline-flex items-center gap-1 text-xs tabular-nums text-slate-500"><Clock3 className="h-3.5 w-3.5" />{updatedAt}</span> : null}
          </div>
          <p className="mt-1 text-pretty leading-5 text-slate-600">
            {importNeeded
              ? (language === 'ru' && dataHealth.reason ? dataHealth.reason : missing.length ? copy.missing : copy.stale)
              : copy.current}
          </p>
        </div>
      </div>
      {importNeeded && showImportAction ? (
        <Button type="button" onClick={onImport} className="min-h-11 shrink-0 gap-2 transition-transform active:scale-[0.96]">
          {copy.upload}
          <ArrowRight className="h-4 w-4 rtl:rotate-180" />
        </Button>
      ) : null}
    </section>
  );
};
