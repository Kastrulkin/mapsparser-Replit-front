import type { Language } from './LanguageContext';

type DashboardNavigationCopy = {
  operator: string;
  operatorHint: string;
  content: string;
  contentHint: string;
  agents: string;
  agentsHint: string;
  partnerships: string;
  partnershipsHint: string;
  expand: string;
  collapse: string;
};

const copy: Record<Language, DashboardNavigationCopy> = {
  ru: { operator: 'Оператор', operatorHint: 'Управляйте LocalOS через единый чат: сводки, действия и безопасные следующие шаги.', content: 'Контент', contentHint: 'Календарь публикаций: что готово, что проверить и что выйдет дальше.', agents: 'Агенты', agentsHint: 'Передавайте повторяющиеся задачи агентам с результатами и ручными подтверждениями.', partnerships: 'Поиск партнёров', partnershipsHint: 'Находите партнёров и ведите кандидатов от отбора до ответа.', expand: 'Развернуть меню', collapse: 'Свернуть меню' },
  en: { operator: 'Operator', operatorHint: 'Control LocalOS through one chat: briefs, actions, and safe next steps.', content: 'Content', contentHint: 'Publication calendar: what is ready, what needs review, and what comes next.', agents: 'Agents', agentsHint: 'Delegate repeatable work to agents with visible results and manual approvals.', partnerships: 'Partner Search', partnershipsHint: 'Find partners and move candidates from selection to response.', expand: 'Expand menu', collapse: 'Collapse menu' },
  fr: { operator: 'Opérateur', operatorHint: 'Pilotez LocalOS depuis un chat : synthèses, actions et prochaines étapes sûres.', content: 'Contenu', contentHint: 'Calendrier éditorial : contenus prêts, à vérifier et à venir.', agents: 'Agents', agentsHint: 'Confiez les tâches répétitives aux agents, avec résultats visibles et validations manuelles.', partnerships: 'Recherche de partenaires', partnershipsHint: 'Trouvez des partenaires et suivez les candidats de la sélection à la réponse.', expand: 'Développer le menu', collapse: 'Réduire le menu' },
  es: { operator: 'Operador', operatorHint: 'Controla LocalOS desde un chat: resúmenes, acciones y próximos pasos seguros.', content: 'Contenido', contentHint: 'Calendario editorial: qué está listo, qué revisar y qué viene después.', agents: 'Agentes', agentsHint: 'Delega tareas repetitivas con resultados visibles y aprobaciones manuales.', partnerships: 'Buscar socios', partnershipsHint: 'Encuentra socios y acompaña a los candidatos desde la selección hasta la respuesta.', expand: 'Expandir menú', collapse: 'Contraer menú' },
  el: { operator: 'Χειριστής', operatorHint: 'Διαχειριστείτε το LocalOS από μία συνομιλία: σύνοψη, ενέργειες και ασφαλή επόμενα βήματα.', content: 'Περιεχόμενο', contentHint: 'Ημερολόγιο δημοσιεύσεων: τι είναι έτοιμο, τι χρειάζεται έλεγχο και τι ακολουθεί.', agents: 'Πράκτορες', agentsHint: 'Αναθέστε επαναλαμβανόμενες εργασίες με ορατά αποτελέσματα και χειροκίνητες εγκρίσεις.', partnerships: 'Αναζήτηση συνεργατών', partnershipsHint: 'Βρείτε συνεργάτες και παρακολουθήστε τους υποψηφίους από την επιλογή έως την απάντηση.', expand: 'Ανάπτυξη μενού', collapse: 'Σύμπτυξη μενού' },
  de: { operator: 'Operator', operatorHint: 'Steuern Sie LocalOS über einen Chat: Übersichten, Aktionen und sichere nächste Schritte.', content: 'Inhalte', contentHint: 'Redaktionskalender: bereit, zu prüfen und als Nächstes geplant.', agents: 'Agenten', agentsHint: 'Delegieren Sie wiederkehrende Aufgaben mit sichtbaren Ergebnissen und manuellen Freigaben.', partnerships: 'Partnersuche', partnershipsHint: 'Finden Sie Partner und begleiten Sie Kandidaten von der Auswahl bis zur Antwort.', expand: 'Menü erweitern', collapse: 'Menü einklappen' },
  th: { operator: 'ผู้ดำเนินการ', operatorHint: 'ควบคุม LocalOS ผ่านแชตเดียว: สรุป การดำเนินการ และขั้นตอนถัดไปที่ปลอดภัย', content: 'คอนเทนต์', contentHint: 'ปฏิทินเผยแพร่: สิ่งที่พร้อม สิ่งที่ต้องตรวจ และสิ่งที่จะตามมา', agents: 'เอเจนต์', agentsHint: 'มอบหมายงานซ้ำให้อัตโนมัติ พร้อมผลลัพธ์ที่เห็นได้และการอนุมัติด้วยคน', partnerships: 'ค้นหาพาร์ทเนอร์', partnershipsHint: 'ค้นหาพาร์ทเนอร์และติดตามผู้สมัครตั้งแต่คัดเลือกจนถึงตอบกลับ', expand: 'ขยายเมนู', collapse: 'ย่อเมนู' },
  ar: { operator: 'المشغّل', operatorHint: 'أدر LocalOS عبر محادثة واحدة: ملخصات وإجراءات وخطوات تالية آمنة.', content: 'المحتوى', contentHint: 'تقويم النشر: ما هو جاهز وما يحتاج مراجعة وما يأتي لاحقًا.', agents: 'الوكلاء', agentsHint: 'فوّض الأعمال المتكررة مع نتائج واضحة وموافقات يدوية.', partnerships: 'البحث عن شركاء', partnershipsHint: 'اعثر على شركاء وتابع المرشحين من الاختيار حتى الرد.', expand: 'توسيع القائمة', collapse: 'طي القائمة' },
  ha: { operator: 'Mai gudanarwa', operatorHint: 'Sarrafa LocalOS ta hira guda: taƙaitawa, ayyuka da matakai masu aminci.', content: 'Abun ciki', contentHint: 'Kalanda na wallafawa: abin da ya shirya, abin dubawa da abin da zai biyo baya.', agents: 'Wakilai', agentsHint: 'Miƙa ayyukan maimaituwa ga wakilai tare da sakamako bayyane da amincewar mutum.', partnerships: 'Neman abokan hulɗa', partnershipsHint: 'Nemo abokan hulɗa kuma bi candidates daga zaɓe zuwa amsa.', expand: 'Faɗaɗa menu', collapse: 'Rufe menu' },
  tr: { operator: 'Operatör', operatorHint: 'LocalOS’u tek sohbetten yönetin: özetler, eylemler ve güvenli sonraki adımlar.', content: 'İçerik', contentHint: 'Yayın takvimi: hazır olanlar, kontrol edilecekler ve sıradakiler.', agents: 'Ajanlar', agentsHint: 'Tekrarlanan işleri görünür sonuçlar ve manuel onaylarla ajanlara devredin.', partnerships: 'İş ortağı arama', partnershipsHint: 'İş ortakları bulun ve adayları seçimden yanıta kadar takip edin.', expand: 'Menüyü genişlet', collapse: 'Menüyü daralt' },
};

export const getDashboardNavigationCopy = (language: Language) => copy[language];
