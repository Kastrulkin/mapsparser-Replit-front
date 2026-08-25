from copy import deepcopy
from typing import Any, Dict, List

from services.agent_blueprint_draft_builder import compile_agent_blueprint
from services.agent_compiled_artifact import build_compiled_artifact_candidate
from services.agent_template_certification import evaluate_template_certification
from services.agent_template_evidence import load_template_certification_evidence
from services.agent_workflow_dsl import build_workflow_dsl_document, validate_workflow_dsl_document


TEMPLATE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "daily_owner_digest",
        "version": "1.0.0",
        "name": "Ежедневная сводка владельцу",
        "business_result": "К началу дня владелец видит один короткий список отклонений и задач, требующих решения.",
        "vertical": "operations",
        "prompt": "Каждый день собирай короткий внутренний отчёт: что требует внимания по отзывам, новостям, услугам, партнёрствам и финансам. Ничего не отправляй клиентам.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "negative_review_reply",
        "version": "1.0.0",
        "name": "Черновики ответов на негативные отзывы",
        "business_result": "Менеджер получает готовые черновики ответов и публикует их только после проверки.",
        "vertical": "reputation",
        "prompt": "Найди негативные отзывы без ответа и подготовь короткие черновики ответов в стиле компании. Публикация только после ручного подтверждения.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "service_seo_cleanup",
        "version": "1.0.0",
        "name": "SEO-проверка услуг",
        "business_result": "Владелец получает приоритетный список слабых названий, дублей и пустых описаний.",
        "vertical": "local_seo",
        "prompt": "Проверь услуги: слабые названия, пустые описания, дубли и SEO-ключи. Подготовь список правок для проверки.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "card_posts_from_signals",
        "version": "1.0.0",
        "name": "Новости из бизнес-сигналов",
        "business_result": "Контент-менеджер получает три черновика новостей на основе реальных данных бизнеса.",
        "vertical": "content",
        "prompt": "Раз в неделю подготовь 3 новости для карточек на основе услуг, отзывов, сезонности и текущих задач. Только черновики.",
        "required_connections": [],
        "risk_level": "low",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "tomorrow_bookings_check",
        "version": "1.0.0",
        "name": "Проверка записей на завтра",
        "business_result": "Администратор заранее видит записи без предоплаты и риски отмены.",
        "vertical": "appointments",
        "prompt": "Каждый вечер проверяй записи на завтра: кто без предоплаты, где есть риск отмены и кому нужен ручной follow-up. Не отправляй сообщения автоматически.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "google_sheets_business_result",
        "version": "1.0.0",
        "name": "Результат из Google Sheets",
        "business_result": "Ответственный получает нормализованную сводку новых строк таблицы и список исключений.",
        "vertical": "operations",
        "prompt": "Каждый вечер читай новые строки Google Sheets, нормализуй их и подготовь внутреннюю сводку с исключениями. Ничего не записывай обратно.",
        "required_connections": ["google_sheets"],
        "risk_level": "medium",
        "certification_status": "beta",
        "pilot_required": True,
    },
    {
        "key": "partnership_outreach_draft",
        "version": "1.0.0",
        "name": "Черновик партнёрского предложения",
        "business_result": "Менеджер получает квалифицированный список партнёров и персональные черновики первого контакта.",
        "vertical": "partnerships",
        "prompt": "Возьми потенциальных партнёров, отсей нерелевантных и подготовь первое письмо и конкретное предложение. Отправка только после подтверждения.",
        "required_connections": [],
        "risk_level": "high",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "competitor_website_monitor",
        "version": "1.0.0",
        "name": "Мониторинг сайта конкурента",
        "business_result": "Владелец получает только значимые изменения цен, акций или меню.",
        "vertical": "market_intelligence",
        "prompt": "Открывай сайт конкурента, проверяй изменения в ценах, акциях или меню и готовь внутренний короткий отчёт.",
        "required_connections": ["browser_use"],
        "risk_level": "medium",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "faq_miner",
        "version": "1.0.0",
        "name": "FAQ из обращений клиентов",
        "business_result": "Команда получает сгруппированные повторяющиеся вопросы и новые черновики ответов.",
        "vertical": "customer_service",
        "prompt": "Собирай повторяющиеся вопросы клиентов из доступных обращений, группируй их и предлагай новые ответы для FAQ.",
        "required_connections": [],
        "risk_level": "medium",
        "certification_status": "draft",
        "pilot_required": True,
    },
    {
        "key": "finance_import_assistant",
        "version": "1.0.0",
        "name": "Подготовка импорта расходов",
        "business_result": "Финансист получает проверяемые предложения категорий до применения транзакций.",
        "vertical": "finance",
        "prompt": "Читай таблицу расходов, нормализуй категории и подготовь предложения для Финансов LocalOS. Применение только после ручного подтверждения.",
        "required_connections": ["google_sheets"],
        "risk_level": "high",
        "certification_status": "draft",
        "pilot_required": True,
    },
]


TEMPLATE_LOCALIZED_CONTENT: Dict[str, Dict[str, Dict[str, str]]] = {
    "daily_owner_digest": {
        "en": {"name": "Daily owner digest", "business_result": "The owner starts the day with one short list of exceptions and decisions."},
        "tr": {"name": "İşletme sahibi için günlük özet", "business_result": "İşletme sahibi güne istisnaları ve kararları gösteren tek bir kısa listeyle başlar."},
    },
    "negative_review_reply": {
        "en": {"name": "Negative-review reply drafts", "business_result": "The manager receives ready-to-review replies and publishes only after approval."},
        "tr": {"name": "Olumsuz yorum yanıt taslakları", "business_result": "Yönetici incelemeye hazır yanıtlar alır; yayınlama yalnızca onaydan sonra yapılır."},
    },
    "service_seo_cleanup": {
        "en": {"name": "Service SEO check", "business_result": "The owner gets a prioritized list of weak names, duplicates, and missing descriptions."},
        "tr": {"name": "Hizmet SEO kontrolü", "business_result": "İşletme sahibi zayıf adlar, tekrarlar ve eksik açıklamalar için öncelikli bir liste alır."},
    },
    "card_posts_from_signals": {
        "en": {"name": "Posts from business signals", "business_result": "The content manager receives three drafts grounded in real business data."},
        "tr": {"name": "İşletme sinyallerinden gönderiler", "business_result": "İçerik yöneticisi gerçek işletme verilerine dayalı üç taslak alır."},
    },
    "tomorrow_bookings_check": {
        "en": {"name": "Tomorrow's bookings check", "business_result": "The administrator sees missing prepayments and cancellation risks in advance."},
        "tr": {"name": "Yarının rezervasyonlarını kontrol et", "business_result": "Yönetici eksik ön ödemeleri ve iptal risklerini önceden görür."},
    },
    "google_sheets_business_result": {
        "en": {"name": "Business result from Google Sheets", "business_result": "The owner receives a normalized digest of new rows and exceptions."},
        "tr": {"name": "Google E-Tablolar'dan işletme sonucu", "business_result": "Sorumlu kişi yeni satırların ve istisnaların normalleştirilmiş özetini alır."},
    },
    "partnership_outreach_draft": {
        "en": {"name": "Partnership proposal draft", "business_result": "The manager gets qualified partners and personalized first-contact drafts."},
        "tr": {"name": "İş ortaklığı teklifi taslağı", "business_result": "Yönetici uygun iş ortaklarını ve kişiselleştirilmiş ilk temas taslaklarını alır."},
    },
    "competitor_website_monitor": {
        "en": {"name": "Competitor website monitor", "business_result": "The owner sees only meaningful price, promotion, or menu changes."},
        "tr": {"name": "Rakip web sitesi takibi", "business_result": "İşletme sahibi yalnızca önemli fiyat, kampanya veya menü değişikliklerini görür."},
    },
    "faq_miner": {
        "en": {"name": "FAQ from customer conversations", "business_result": "The team receives grouped recurring questions and new answer drafts."},
        "tr": {"name": "Müşteri görüşmelerinden SSS", "business_result": "Ekip tekrarlanan soruların gruplarını ve yeni yanıt taslaklarını alır."},
    },
    "finance_import_assistant": {
        "en": {"name": "Expense import preparation", "business_result": "Finance receives reviewable category suggestions before transactions are applied."},
        "tr": {"name": "Gider içe aktarma hazırlığı", "business_result": "Finans ekibi işlemler uygulanmadan önce incelenebilir kategori önerileri alır."},
    },
}

TEMPLATE_ADDITIONAL_LOCALIZED_CONTENT: Dict[str, Dict[str, Dict[str, str]]] = {
    "daily_owner_digest": {
        "ru": {"name": "Ежедневная сводка владельцу", "business_result": "К началу дня владелец видит один короткий список отклонений и задач, требующих решения."},
        "fr": {"name": "Synthèse quotidienne du dirigeant", "business_result": "Le dirigeant commence la journée avec une courte liste d’écarts et de décisions."},
        "es": {"name": "Resumen diario para el propietario", "business_result": "El propietario empieza el día con una lista breve de excepciones y decisiones."},
        "el": {"name": "Ημερήσια σύνοψη ιδιοκτήτη", "business_result": "Ο ιδιοκτήτης ξεκινά τη μέρα με μια σύντομη λίστα αποκλίσεων και αποφάσεων."},
        "de": {"name": "Tägliche Inhaberübersicht", "business_result": "Der Inhaber startet mit einer kurzen Liste von Abweichungen und Entscheidungen in den Tag."},
        "th": {"name": "สรุปรายวันสำหรับเจ้าของ", "business_result": "เจ้าของเริ่มวันด้วยรายการสั้น ๆ ของข้อยกเว้นและเรื่องที่ต้องตัดสินใจ"},
        "ar": {"name": "ملخص يومي للمالك", "business_result": "يبدأ المالك يومه بقائمة قصيرة من الاستثناءات والقرارات المطلوبة."},
        "ha": {"name": "Takaitaccen bayani na yau da kullum ga mai kasuwanci", "business_result": "Mai kasuwanci yana fara rana da gajeren jerin abubuwan da suka bambanta da shawarar da ake bukata."},
    },
    "negative_review_reply": {
        "ru": {"name": "Черновики ответов на негативные отзывы", "business_result": "Менеджер получает готовые черновики ответов и публикует их только после проверки."},
        "fr": {"name": "Brouillons de réponse aux avis négatifs", "business_result": "Le responsable reçoit des réponses prêtes à vérifier et ne publie qu’après validation."},
        "es": {"name": "Borradores para reseñas negativas", "business_result": "El responsable recibe respuestas listas para revisar y solo publica tras aprobarlas."},
        "el": {"name": "Προσχέδια απαντήσεων σε αρνητικές κριτικές", "business_result": "Ο υπεύθυνος λαμβάνει έτοιμες απαντήσεις και δημοσιεύει μόνο μετά την έγκριση."},
        "de": {"name": "Antwortentwürfe für negative Bewertungen", "business_result": "Die Leitung erhält prüfbereite Antworten und veröffentlicht erst nach Freigabe."},
        "th": {"name": "ร่างคำตอบสำหรับรีวิวเชิงลบ", "business_result": "ผู้จัดการได้รับคำตอบที่พร้อมตรวจสอบและเผยแพร่หลังอนุมัติเท่านั้น"},
        "ar": {"name": "مسودات الرد على المراجعات السلبية", "business_result": "يتلقى المدير ردودًا جاهزة للمراجعة ولا ينشرها إلا بعد الموافقة."},
        "ha": {"name": "Daftarin amsa ga reviews marasa kyau", "business_result": "Manaja yana samun amsoshin da aka shirya don dubawa kuma ba a wallafa sai bayan amincewa."},
    },
    "service_seo_cleanup": {
        "ru": {"name": "SEO-проверка услуг", "business_result": "Владелец получает приоритетный список слабых названий, дублей и пустых описаний."},
        "fr": {"name": "Contrôle SEO des services", "business_result": "Le dirigeant reçoit une liste priorisée des noms faibles, doublons et descriptions manquantes."},
        "es": {"name": "Revisión SEO de servicios", "business_result": "El propietario recibe una lista priorizada de nombres débiles, duplicados y descripciones vacías."},
        "el": {"name": "Έλεγχος SEO υπηρεσιών", "business_result": "Ο ιδιοκτήτης λαμβάνει λίστα προτεραιότητας με αδύναμα ονόματα, διπλότυπα και κενές περιγραφές."},
        "de": {"name": "SEO-Prüfung der Leistungen", "business_result": "Der Inhaber erhält eine priorisierte Liste schwacher Namen, Duplikate und fehlender Beschreibungen."},
        "th": {"name": "ตรวจ SEO ของบริการ", "business_result": "เจ้าของได้รับรายการเรียงลำดับความสำคัญของชื่อที่ควรปรับ รายการซ้ำ และคำอธิบายที่ขาดหาย"},
        "ar": {"name": "فحص تحسين محركات البحث للخدمات", "business_result": "يتلقى المالك قائمة مرتبة بالأسماء الضعيفة والتكرارات والأوصاف الناقصة."},
        "ha": {"name": "Binciken SEO na ayyuka", "business_result": "Mai kasuwanci yana samun jerin sunaye marasa ƙarfi, kwafi da bayanan da suka ɓace bisa fifiko."},
    },
    "card_posts_from_signals": {
        "ru": {"name": "Новости из бизнес-сигналов", "business_result": "Контент-менеджер получает три черновика новостей на основе реальных данных бизнеса."},
        "fr": {"name": "Publications issues des signaux du commerce", "business_result": "Le responsable de contenu reçoit trois brouillons fondés sur les données réelles de l’entreprise."},
        "es": {"name": "Publicaciones a partir de señales del negocio", "business_result": "El responsable de contenido recibe tres borradores basados en datos reales del negocio."},
        "el": {"name": "Αναρτήσεις από επιχειρηματικά σήματα", "business_result": "Ο υπεύθυνος περιεχομένου λαμβάνει τρία προσχέδια βασισμένα σε πραγματικά δεδομένα."},
        "de": {"name": "Beiträge aus Geschäftssignalen", "business_result": "Das Content-Team erhält drei Entwürfe auf Basis realer Geschäftsdaten."},
        "th": {"name": "โพสต์จากสัญญาณธุรกิจ", "business_result": "ผู้ดูแลคอนเทนต์ได้รับร่างสามฉบับที่อ้างอิงข้อมูลธุรกิจจริง"},
        "ar": {"name": "منشورات من إشارات النشاط", "business_result": "يتلقى مسؤول المحتوى ثلاث مسودات مبنية على بيانات النشاط الفعلية."},
        "ha": {"name": "Rubuce-rubuce daga alamomin kasuwanci", "business_result": "Mai kula da abun ciki yana samun daftari uku da suka dogara da ainihin bayanan kasuwanci."},
    },
    "tomorrow_bookings_check": {
        "ru": {"name": "Проверка записей на завтра", "business_result": "Администратор заранее видит записи без предоплаты и риски отмены."},
        "fr": {"name": "Contrôle des réservations de demain", "business_result": "L’administrateur repère à l’avance les acomptes manquants et les risques d’annulation."},
        "es": {"name": "Revisión de las reservas de mañana", "business_result": "El administrador detecta con antelación anticipos pendientes y riesgos de cancelación."},
        "el": {"name": "Έλεγχος αυριανών κρατήσεων", "business_result": "Ο διαχειριστής βλέπει έγκαιρα τις ελλείψεις προκαταβολών και τους κινδύνους ακύρωσης."},
        "de": {"name": "Prüfung der morgigen Termine", "business_result": "Die Verwaltung sieht fehlende Vorauszahlungen und Stornorisiken frühzeitig."},
        "th": {"name": "ตรวจการจองของวันพรุ่งนี้", "business_result": "ผู้ดูแลเห็นรายการที่ยังไม่ชำระล่วงหน้าและความเสี่ยงในการยกเลิกล่วงหน้า"},
        "ar": {"name": "فحص حجوزات الغد", "business_result": "يرى المسؤول مسبقًا الدفعات المقدمة الناقصة ومخاطر الإلغاء."},
        "ha": {"name": "Binciken ajiyar gobe", "business_result": "Mai gudanarwa yana ganin rashin biyan kuɗin farko da haɗarin soke wa tun da wuri."},
    },
    "google_sheets_business_result": {
        "ru": {"name": "Результат из Google Sheets", "business_result": "Ответственный получает нормализованную сводку новых строк таблицы и список исключений."},
        "fr": {"name": "Résultat métier depuis Google Sheets", "business_result": "Le responsable reçoit une synthèse normalisée des nouvelles lignes et des exceptions."},
        "es": {"name": "Resultado de negocio desde Google Sheets", "business_result": "El responsable recibe un resumen normalizado de nuevas filas y excepciones."},
        "el": {"name": "Επιχειρηματικό αποτέλεσμα από Google Sheets", "business_result": "Ο υπεύθυνος λαμβάνει κανονικοποιημένη σύνοψη νέων γραμμών και εξαιρέσεων."},
        "de": {"name": "Geschäftsergebnis aus Google Sheets", "business_result": "Die zuständige Person erhält eine normalisierte Übersicht neuer Zeilen und Ausnahmen."},
        "th": {"name": "ผลลัพธ์ธุรกิจจาก Google Sheets", "business_result": "ผู้รับผิดชอบได้รับสรุปแถวใหม่และข้อยกเว้นในรูปแบบมาตรฐาน"},
        "ar": {"name": "نتيجة العمل من Google Sheets", "business_result": "يتلقى المسؤول ملخصًا موحدًا للصفوف الجديدة والاستثناءات."},
        "ha": {"name": "Sakamakon kasuwanci daga Google Sheets", "business_result": "Mai alhaki yana samun takaitaccen sabbin layuka da abubuwan da suka bambanta a tsari ɗaya."},
    },
    "partnership_outreach_draft": {
        "ru": {"name": "Черновик партнёрского предложения", "business_result": "Менеджер получает квалифицированный список партнёров и персональные черновики первого контакта."},
        "fr": {"name": "Brouillon de proposition de partenariat", "business_result": "Le responsable reçoit des partenaires qualifiés et des premiers messages personnalisés."},
        "es": {"name": "Borrador de propuesta de colaboración", "business_result": "El responsable recibe socios cualificados y borradores personalizados para el primer contacto."},
        "el": {"name": "Προσχέδιο πρότασης συνεργασίας", "business_result": "Ο υπεύθυνος λαμβάνει κατάλληλους συνεργάτες και εξατομικευμένα προσχέδια πρώτης επαφής."},
        "de": {"name": "Entwurf eines Partnerschaftsangebots", "business_result": "Die Leitung erhält qualifizierte Partner und personalisierte Entwürfe für den Erstkontakt."},
        "th": {"name": "ร่างข้อเสนอความร่วมมือ", "business_result": "ผู้จัดการได้รับรายชื่อพันธมิตรที่ผ่านการคัดเลือกและร่างข้อความติดต่อครั้งแรกเฉพาะราย"},
        "ar": {"name": "مسودة عرض شراكة", "business_result": "يتلقى المدير شركاء مؤهلين ومسودات مخصصة للتواصل الأول."},
        "ha": {"name": "Daftarin tayin haɗin gwiwa", "business_result": "Manaja yana samun abokan haɗin gwiwa da suka dace da daftarin saƙon farko na musamman."},
    },
    "competitor_website_monitor": {
        "ru": {"name": "Мониторинг сайта конкурента", "business_result": "Владелец получает только значимые изменения цен, акций или меню."},
        "fr": {"name": "Suivi du site d’un concurrent", "business_result": "Le dirigeant ne voit que les changements importants de prix, promotions ou menu."},
        "es": {"name": "Monitor del sitio de la competencia", "business_result": "El propietario solo ve cambios relevantes en precios, promociones o menú."},
        "el": {"name": "Παρακολούθηση ιστοτόπου ανταγωνιστή", "business_result": "Ο ιδιοκτήτης βλέπει μόνο σημαντικές αλλαγές σε τιμές, προσφορές ή μενού."},
        "de": {"name": "Beobachtung einer Wettbewerber-Website", "business_result": "Der Inhaber sieht nur relevante Änderungen an Preisen, Aktionen oder Sortiment."},
        "th": {"name": "ติดตามเว็บไซต์คู่แข่ง", "business_result": "เจ้าของเห็นเฉพาะการเปลี่ยนแปลงสำคัญของราคา โปรโมชัน หรือเมนู"},
        "ar": {"name": "مراقبة موقع منافس", "business_result": "يرى المالك فقط التغييرات المهمة في الأسعار أو العروض أو القائمة."},
        "ha": {"name": "Sa ido kan shafin abokin hamayya", "business_result": "Mai kasuwanci yana ganin muhimman canje-canjen farashi, talla ko menu kawai."},
    },
    "faq_miner": {
        "ru": {"name": "FAQ из обращений клиентов", "business_result": "Команда получает сгруппированные повторяющиеся вопросы и новые черновики ответов."},
        "fr": {"name": "FAQ à partir des échanges clients", "business_result": "L’équipe reçoit les questions récurrentes regroupées et de nouveaux brouillons de réponse."},
        "es": {"name": "FAQ a partir de conversaciones con clientes", "business_result": "El equipo recibe preguntas frecuentes agrupadas y nuevos borradores de respuesta."},
        "el": {"name": "Συχνές ερωτήσεις από συνομιλίες πελατών", "business_result": "Η ομάδα λαμβάνει ομαδοποιημένες επαναλαμβανόμενες ερωτήσεις και νέα προσχέδια απαντήσεων."},
        "de": {"name": "FAQ aus Kundengesprächen", "business_result": "Das Team erhält gruppierte wiederkehrende Fragen und neue Antwortentwürfe."},
        "th": {"name": "คำถามที่พบบ่อยจากบทสนทนากับลูกค้า", "business_result": "ทีมได้รับคำถามซ้ำที่จัดกลุ่มแล้วและร่างคำตอบใหม่"},
        "ar": {"name": "الأسئلة الشائعة من محادثات العملاء", "business_result": "يتلقى الفريق أسئلة متكررة مجمعة ومسودات إجابات جديدة."},
        "ha": {"name": "FAQ daga tattaunawar kwastomomi", "business_result": "Ƙungiya tana samun tambayoyin da ake maimaitawa a rukuni da sabbin daftarin amsa."},
    },
    "finance_import_assistant": {
        "ru": {"name": "Подготовка импорта расходов", "business_result": "Финансист получает проверяемые предложения категорий до применения транзакций."},
        "fr": {"name": "Préparation de l’import des dépenses", "business_result": "La finance reçoit des suggestions de catégories à vérifier avant l’application des transactions."},
        "es": {"name": "Preparación de la importación de gastos", "business_result": "Finanzas recibe sugerencias de categorías revisables antes de aplicar las transacciones."},
        "el": {"name": "Προετοιμασία εισαγωγής εξόδων", "business_result": "Το οικονομικό τμήμα λαμβάνει προτάσεις κατηγοριών για έλεγχο πριν εφαρμοστούν οι συναλλαγές."},
        "de": {"name": "Vorbereitung des Ausgabenimports", "business_result": "Die Finanzabteilung erhält prüfbare Kategorievorschläge, bevor Transaktionen übernommen werden."},
        "th": {"name": "เตรียมนำเข้าค่าใช้จ่าย", "business_result": "ฝ่ายการเงินได้รับคำแนะนำหมวดหมู่ที่ตรวจสอบได้ก่อนนำธุรกรรมไปใช้"},
        "ar": {"name": "إعداد استيراد المصروفات", "business_result": "يتلقى قسم المالية اقتراحات فئات قابلة للمراجعة قبل تطبيق المعاملات."},
        "ha": {"name": "Shirya shigo da kuɗaɗen kashewa", "business_result": "Sashen kuɗi yana samun shawarwarin rukuni don dubawa kafin a aiwatar da ma’amaloli."},
    },
}

for template_key, localized_content in TEMPLATE_ADDITIONAL_LOCALIZED_CONTENT.items():
    TEMPLATE_LOCALIZED_CONTENT[template_key].update(localized_content)


FIRST_WAVE_TEMPLATE_PRESETS: Dict[str, Dict[str, Any]] = {
    "daily_owner_digest": {
        "trigger": "schedule.daily",
        "schedule": {"time": "09:00", "timezone": "business_timezone"},
        "sources": ["reviews", "services", "content", "partnerships", "finance"],
        "model_preset": "owner_digest",
        "result_format": "owner_digest_v1",
        "max_items": 25,
    },
    "negative_review_reply": {
        "trigger": "manual.run",
        "sources": ["external_reviews", "business_profile"],
        "model_preset": "negative_review_reply_drafts",
        "result_format": "review_reply_drafts_v1",
        "max_items": 12,
    },
    "service_seo_cleanup": {
        "trigger": "manual.run",
        "sources": ["services", "business_profile"],
        "model_preset": "service_seo_audit",
        "result_format": "service_seo_audit_v1",
        "max_items": 100,
    },
    "card_posts_from_signals": {
        "trigger": "schedule.weekly",
        "schedule": {"weekday": 1, "time": "10:00", "timezone": "business_timezone"},
        "sources": ["services", "external_reviews", "business_profile", "content"],
        "model_preset": "card_post_drafts",
        "result_format": "card_post_drafts_v1",
        "max_items": 30,
    },
    "tomorrow_bookings_check": {
        "trigger": "schedule.daily",
        "schedule": {"time": "18:00", "timezone": "business_timezone"},
        "sources": ["appointments", "business_profile"],
        "model_preset": "tomorrow_booking_risks",
        "result_format": "tomorrow_booking_risks_v1",
        "max_items": 100,
        "internal_read_capability": "appointments.read",
    },
    "google_sheets_business_result": {
        "trigger": "schedule.daily",
        "schedule": {"time": "18:00", "timezone": "business_timezone"},
        "sources": ["google_sheets"],
        "model_preset": "sheet_business_digest",
        "result_format": "sheet_business_digest_v1",
        "max_items": 100,
        "read_binding": {
            "key": "google_sheets_read",
            "provider": "google_sheets",
            "direction": "external_read",
            "required": True,
            "approval_required": False,
            "required_config": ["spreadsheet_id", "sheet_name"],
            "default_config": {"sheet_name": "Sheet1"},
            "capability": "google_sheets.read_rows",
        },
    },
}


FIRST_WAVE_GOLDEN_CASES: Dict[str, List[Dict[str, Any]]] = {
    "daily_owner_digest": [
        {
            "key": "negative_review_and_finance_exception",
            "input_fixture": {
                "reviews": [{"id": "review-1", "rating": 2, "text": "Долго ждал", "response_text": ""}],
                "finance": [{"id": "finance-1", "transaction_type": "expense", "amount": 12000}],
            },
            "expected": {"source_refs_include": ["review-1", "finance-1"], "requires_owner_decision": True},
        }
    ],
    "negative_review_reply": [
        {
            "key": "one_unanswered_negative_review",
            "input_fixture": {"reviews": [{"id": "review-1", "rating": 1, "text": "Не дождался заказа", "response_text": ""}]},
            "expected": {"drafts_for": ["review-1"], "draft_only": True, "forbidden_claims": ["гарантируем возврат", "уже вернули деньги"]},
        }
    ],
    "service_seo_cleanup": [
        {
            "key": "duplicate_and_empty_service_descriptions",
            "input_fixture": {
                "services": [
                    {"id": "service-1", "name": "Стрижка", "description": ""},
                    {"id": "service-2", "name": "Стрижка", "description": "Коротко"},
                ]
            },
            "expected": {"flag_ids": ["service-1", "service-2"], "localos_write_performed": False},
        }
    ],
    "card_posts_from_signals": [
        {
            "key": "three_fact_grounded_post_drafts",
            "input_fixture": {
                "services": [{"id": "service-1", "name": "Семейный ужин", "description": "По пятницам"}],
                "reviews": [{"id": "review-1", "rating": 5, "text": "Удобно приходить с детьми"}],
            },
            "expected": {"draft_count": 3, "draft_only": True, "invented_promotions_allowed": False},
        }
    ],
    "tomorrow_bookings_check": [
        {
            "key": "booking_without_prepayment",
            "input_fixture": {
                "appointments": [{"id": "appointment-1", "date_range": "tomorrow", "status": "confirmed", "prepayment": False}]
            },
            "expected": {"flag_ids": ["appointment-1"], "communications_created": False, "personal_data_in_model_prompt": False},
        }
    ],
    "google_sheets_business_result": [
        {
            "key": "valid_row_and_incomplete_row",
            "input_fixture": {
                "rows": [
                    {"row_id": "row-1", "name": "Заказ 1", "amount": 1500},
                    {"row_id": "row-2", "name": "", "amount": ""},
                ]
            },
            "expected": {"accepted_ids": ["row-1"], "exception_ids": ["row-2"], "provider_write_performed": False},
        }
    ],
}


def build_agent_template_catalog() -> List[Dict[str, Any]]:
    return [_build_template_manifest(definition) for definition in TEMPLATE_DEFINITIONS]


def get_agent_template(template_key: str) -> Dict[str, Any]:
    for item in build_agent_template_catalog():
        if item["key"] == template_key:
            return item
    return {}


def build_agent_from_template(template_key: str) -> Dict[str, Any]:
    for definition in TEMPLATE_DEFINITIONS:
        if definition["key"] != template_key:
            continue
        draft = _build_first_wave_template_draft(definition)
        if not draft:
            draft = compile_agent_blueprint(str(definition["prompt"]), use_ai=False)
        return {
            "definition": deepcopy(definition),
            "draft": draft,
        }
    return {}


def _build_template_manifest(definition: Dict[str, Any]) -> Dict[str, Any]:
    draft = build_agent_from_template(str(definition["key"]))["draft"]
    version_payload = deepcopy(draft["version_payload"])
    metadata = deepcopy(draft["metadata"])
    workflow_dsl = build_workflow_dsl_document(version_payload, metadata)
    validation = validate_workflow_dsl_document(workflow_dsl)
    compiled_candidate = metadata.get("compiled_artifact_candidate")
    compiled_valid = bool(compiled_candidate and compiled_candidate.get("validation", {}).get("valid"))
    schema_gate = bool(validation.get("valid")) and compiled_valid
    security_gate = (
        version_payload.get("side_effects_performed") is not True
        and version_payload.get("limits", {}).get("autonomous_external_write_allowed") is not True
        and version_payload.get("limits", {}).get("autonomous_localos_write_allowed") is not True
    )
    fixture_keys = [
        "valid_input",
        "empty_input",
        "malformed_input",
        "missing_connection",
        "expired_oauth",
        "transient_provider_failure",
        "duplicate_idempotency_key",
        "worker_restart",
        "limit_exceeded",
    ]
    gates = {
        "security": {"passed": security_gate, "evidence": "No autonomous external write is allowed"},
        "schema": {"passed": schema_gate, "evidence": "DSL, topology and compiled artifact validation"},
        "execution": {"passed": False, "evidence": "Runtime fixture evidence is required"},
        "accuracy": {"passed": False, "evidence": "Golden dataset and pilot scoring are required"},
    }
    manifest = {
        "key": definition["key"],
        "version": definition["version"],
        "name": definition["name"],
        "business_result": definition["business_result"],
        "localized_content": TEMPLATE_LOCALIZED_CONTENT.get(str(definition["key"]), {}),
        "vertical": definition["vertical"],
        "trigger": version_payload.get("trigger") or "manual.run",
        "inputs_schema": version_payload.get("inputs_schema") or {},
        "workflow_dsl": workflow_dsl,
        "required_connections": definition.get("required_connections") or [],
        "approval_policy": version_payload.get("approval_policy") or {},
        "limits": version_payload.get("limits") or {},
        "output_schema": version_payload.get("output_schema") or {},
        "risk_level": definition["risk_level"],
        "certification_status": definition["certification_status"],
        "certification_gates": gates,
        "certification_evidence": load_template_certification_evidence(str(definition["key"]), str(definition["version"])),
        "fixtures": [{"key": key, "status": "pending"} for key in fixture_keys],
        "golden_results": deepcopy(FIRST_WAVE_GOLDEN_CASES.get(str(definition["key"]), [])),
        "creation_prompt": definition["prompt"],
        "category": draft["category"],
    }
    manifest["certification_evaluation"] = evaluate_template_certification(manifest, manifest["certification_evidence"])
    manifest["certification_evidence"]["certification_decision"] = (
        "certified" if manifest["certification_evaluation"]["certified"] else "pilot_evidence_required"
    )
    return manifest


def _build_first_wave_template_draft(definition: Dict[str, Any]) -> Dict[str, Any]:
    preset = FIRST_WAVE_TEMPLATE_PRESETS.get(str(definition.get("key") or ""))
    if not preset:
        return {}
    source_step = {
        "key": "collect_registered_sources",
        "type": "artifact",
        "title": "Собрать разрешённые данные",
        "artifact_type": "agent_input_plan",
        "payload": {
            "status": "ready",
            "sources": deepcopy(preset["sources"]),
            "source_scope": "registered_business_sources_only",
            "external_dispatch_performed": False,
        },
    }
    steps = [source_step]
    bindings = []
    capabilities = []
    read_binding = preset.get("read_binding")
    if isinstance(read_binding, dict):
        binding = deepcopy(read_binding)
        binding["trigger"] = preset["trigger"]
        bindings.append(binding)
        capabilities.append(str(binding["capability"]))
        steps = [
            {
                "key": "read_google_sheets",
                "type": "capability",
                "title": "Прочитать новые строки таблицы",
                "capability": "google_sheets.read_rows",
                "requires_approval": False,
                "payload": {
                    "integration_binding": "google_sheets_read",
                    "limit": preset["max_items"],
                    "provider_write_performed": False,
                },
                "provider": "native_localos",
                "provider_policy": "localos_envelope",
                "provider_risk_class": "read",
                "provider_approval_class": "none",
            }
        ]
    internal_read_capability = str(preset.get("internal_read_capability") or "").strip()
    if internal_read_capability:
        capabilities.append(internal_read_capability)
        steps = [
            {
                "key": "read_tomorrow_appointments",
                "type": "capability",
                "title": "Прочитать записи на завтра",
                "capability": internal_read_capability,
                "requires_approval": False,
                "payload": {
                    "date_range": "tomorrow",
                    "max_items": preset["max_items"],
                    "provider_write_performed": False,
                },
            }
        ]
    model_step = {
        "key": "prepare_bounded_result",
        "type": "artifact",
        "title": "Подготовить результат по фиксированным правилам",
        "artifact_type": "agent_output_draft",
        "bounded_model_call": True,
        "model_task_key": "agent_bounded_workflow_step",
        "model_preset": preset["model_preset"],
        "purpose": definition["business_result"],
        "input_schema": "registered_business_sources_v1",
        "output_schema": preset["result_format"],
        "fallback": "deterministic_summary_then_human_review",
        "payload": {
            "status": "draft",
            "category": definition["vertical"],
            "format": preset["result_format"],
            "source_step": steps[-1]["key"],
            "source_scope": deepcopy(preset["sources"]),
            "max_items": preset["max_items"],
            "external_dispatch_performed": False,
            "delivery_state": "internal_only",
        },
    }
    steps.extend(
        [
            model_step,
            {
                "key": "save_internal_result",
                "type": "artifact",
                "title": "Сохранить результат в LocalOS",
                "artifact_type": "agent_final_result",
                "payload": {
                    "status": "saved",
                    "source_step": "prepare_bounded_result",
                    "external_dispatch_performed": False,
                    "delivery_state": "internal_only",
                },
            },
        ]
    )
    limits = {
        "max_items_per_run": preset["max_items"],
        "max_model_calls_per_run": 1,
        "autonomous_external_write_allowed": False,
        "autonomous_localos_write_allowed": False,
        "duplicate_policy": "idempotency_key_required",
    }
    version_payload = {
        "goal": definition["prompt"],
        "trigger": preset["trigger"],
        "execution_mode": "scheduled" if str(preset["trigger"]).startswith("schedule.") else "manual",
        "schedule": deepcopy(preset.get("schedule") or {}),
        "mode": "compiled_bounded_result",
        "inputs_schema": {"type": "object", "properties": {"request": {"type": "string"}}},
        "steps": steps,
        "capability_allowlist": capabilities,
        "approval_policy": {
            "required_for": [],
            "external_delivery": "manual_approval_required",
            "mode": "external_actions_only",
        },
        "required_integration_bindings": bindings,
        "limits": limits,
        "output_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "items": {"type": "array"},
                "exceptions": {"type": "array"},
                "drafts": {"type": "array"},
                "source_refs": {"type": "array"},
            },
        },
        "side_effects_performed": False,
    }
    metadata = {
        "builder": "certified_template_registry_v1",
        "compiler": "agent_compiler_v1",
        "compiled_workflow_status": "draft",
        "request_text": definition["prompt"],
        "draft_category": definition["vertical"],
        "data_sources": deepcopy(preset["sources"]),
        "outputs": [preset["result_format"]],
        "approval_boundaries": ["external_delivery"],
        "external_delivery": "approval_required",
        "side_effects": "none",
        "compiled_process": {
            "schema": "compiled_bounded_template_workflow_v1",
            "trigger": preset["trigger"],
            "runtime_truth": "agent_blueprint_versions.steps_json",
            "approval_boundary": "external_actions_only",
        },
        "compiler_contract": {
            "llm_usage": "bounded_registered_runtime_step",
            "runtime_truth": "agent_blueprint_versions.steps_json",
            "runtime_planner_required": False,
            "runtime_model_steps": [
                {
                    "key": model_step["key"],
                    "purpose": model_step["purpose"],
                    "input_schema": model_step["input_schema"],
                    "output_schema": model_step["output_schema"],
                    "fallback": model_step["fallback"],
                    "task_key": model_step["model_task_key"],
                    "preset": model_step["model_preset"],
                }
            ],
            "runtime_llm_required": False,
            "runtime_executes_compiled_steps": True,
        },
        "required_integration_bindings": bindings,
    }
    metadata["compiled_artifact_candidate"] = build_compiled_artifact_candidate(version_payload, metadata)
    metadata["compiled_validation"] = metadata["compiled_artifact_candidate"]["validation"]
    return {
        "category": definition["vertical"],
        "version_payload": version_payload,
        "metadata": metadata,
    }
