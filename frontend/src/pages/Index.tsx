import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Building2,
  CalendarClock,
  Check,
  CircleCheck,
  CircleDollarSign,
  ClipboardCheck,
  Clock3,
  Eye,
  FileCheck2,
  Layers3,
  Loader2,
  MapPinned,
  MessageSquareText,
  Network,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import Footer from "@/components/Footer";
import SeoMeta from "@/components/SeoMeta";
import { PublicBrandBackdrop } from "@/components/PublicBrandBackdrop";
import { Button } from "@/components/ui/button";
import { useLocalizedCases } from "@/content/useLocalizedCollections";
import { Language, useLanguage } from "@/i18n/LanguageContext";
import landingTranslations from "@/i18n/homeLandingTranslations.json";

type TaskCard = {
  title: string;
  description: string;
};

type WorkStep = {
  title: string;
  description: string;
};

type NetworkQuestion = {
  text: string;
  href: string;
};

type NetworkQuestionSet = {
  intro: string;
  sourceNote: string;
  questions: NetworkQuestion[];
};

type ProductPreviewCopy = {
  eyebrow: string;
  title: string;
  active: string;
  items: Array<{
    title: string;
    detail: string;
    status: string;
  }>;
  ownerNote: string;
};

type LandingCopy = {
  metaTitle: string;
  metaDescription: string;
  eyebrow: string;
  title: string;
  intro: string;
  seeTasks: string;
  freeAudit: string;
  formTitle: string;
  formDescription: string;
  emailLabel: string;
  emailPlaceholder: string;
  mapsLabel: string;
  mapsPlaceholder: string;
  submit: string;
  submitting: string;
  success: string;
  error: string;
  scale: string;
  problemTitle: string;
  problemParagraphs: string[];
  networkTitle: string;
  networkSummary: string;
  networkPrivacy: string;
  networkLabels: string[];
  tasksEyebrow: string;
  tasksTitle: string;
  tasksIntro: string;
  tasks: TaskCard[];
  retentionNote: string;
  workEyebrow: string;
  workTitle: string;
  workIntro: string;
  steps: WorkStep[];
  workSummary: string;
  casesEyebrow: string;
  casesTitle: string;
  casesIntro: string;
  situation: string;
  workDone: string;
  result: string;
  allCases: string;
  auditTitle: string;
  auditText: string;
  finalTitle: string;
  finalText: string;
  tryFree: string;
  talkExpert: string;
};

const ruCopy: LandingCopy = {
  metaTitle: "LocalOS — меньше рутины для владельца локального бизнеса",
  metaDescription:
    "LocalOS проверяет карты и отзывы, готовит публикации, анализирует услуги и показатели и выполняет регулярные задачи. Владелец подключается только там, где нужно решение.",
  eyebrow: "LocalOS для локального бизнеса",
  title: "Не держите весь бизнес в голове",
  intro:
    "LocalOS берёт на себя карты, отзывы, публикации, услуги и показатели. ИИ готовит сценарий, вы подтверждаете, скрипт выполняет. Вы подключаетесь, когда нужно решение.",
  seeTasks: "Посмотреть, что можно передать LocalOS",
  freeAudit: "Выбрать из 6 направлений",
  formTitle: "Начните с аудита карт",
  formDescription: "Проверим, как клиенты видят ваш бизнес и что стоит исправить в первую очередь.",
  emailLabel: "Email",
  emailPlaceholder: "you@example.com",
  mapsLabel: "Ссылка на карточку",
  mapsPlaceholder: "https://yandex.ru/maps/org/...",
  submit: "Получить аудит",
  submitting: "Отправляем…",
  success: "Спасибо! Заявка принята.",
  error: "Не удалось отправить заявку. Попробуйте ещё раз.",
  scale: "LocalOS уже работает более чем в 240 точках малого бизнеса — от отдельных компаний до сетей.",
  problemTitle: "Всё завязано на вас",
  problemParagraphs: [
    "Утром — цифры и сотрудники. Днём — клиенты и срочные вопросы. Вечером — то, что не успели за день. Проще сделать самому, чем объяснять и потом проверять.",
    "Так владелец становится самым загруженным сотрудником собственного бизнеса. Кажется, что стоит выключить телефон или уехать на неделю — и работа остановится.",
    "LocalOS снимает повторяющиеся задачи с владельца. Чтобы бизнес продолжал работать, даже когда вы не держите в голове каждый следующий шаг.",
  ],
  networkTitle: "У вас одна точка. Опыт — как у сети",
  networkSummary: "Похожие задачи повторяются в тысячах компаний. LocalOS проверяет найденные решения и сохраняет то, что можно использовать снова.",
  networkPrivacy: "Данные компаний и клиентов остаются закрытыми. Другим бизнесам доступны только общие правила и обезличенные способы работы.",
  networkLabels: ["Один бизнес решает знакомую задачу", "LocalOS проверяет, что сработало", "Другие используют готовый способ"],
  tasksEyebrow: "Боли владельцев",
  tasksTitle: "Знакомо? LocalOS берёт это на себя",
  tasksIntro: "Пять ситуаций из рабочих чатов владельцев. Для каждой — конкретная работа LocalOS.",
  tasks: [
    { title: "Реклама идёт, а стабильной записи всё равно нет", description: "LocalOS проверяет карточки на картах: услуги, цены, фото, публикации и отзывы. Готовит исправления и предложения местным партнёрам. Внешние сообщения — только после вашего подтверждения." },
    { title: "На отзывы отвечаю сам. До публикаций руки не доходят", description: "LocalOS собирает отзывы без ответа, готовит черновики и планирует публикации. Вы проверяете важное и подтверждаете отправку." },
    { title: "Работы много, а средний чек всё равно маленький", description: "LocalOS показывает, какие услуги продаются, как меняются средний чек и загрузка. Готовит план допродаж и кросс-продаж для увеличения среднего чека." },
    { title: "Проще сделать самому, чем объяснять и потом проверять", description: "LocalOS описывает повторяющуюся задачу как сценарий. Вы один раз утверждаете правила, затем скрипт выполняет работу. Если нужно решение, скрипт останавливается." },
    { title: "Клиенты есть, все заняты, а в конце месяца остаются копейки", description: "LocalOS сводит выручку, расходы, средний чек и загрузку. Вы видите динамику показателей и решаете, что проверить первым: цены, загрузку или расходы." },
  ],
  retentionNote: "При подключении клиентских данных LocalOS также может находить клиентов, которые давно не возвращались, и готовить предложения для повторного визита.",
  workEyebrow: "Порядок работы",
  workTitle: "Система работает. Владелец принимает решения",
  workIntro: "LocalOS забирает регулярную работу, но не принимает важные решения за владельца.",
  steps: [
    { title: "Подключаем бизнес", description: "LocalOS получает доступ только к выбранным данным: карточкам, отзывам, услугам, финансовым показателям и подключённым каналам." },
    { title: "Находим работу, которую можно снять с владельца", description: "Система отделяет разовую проблему от задачи, которую нужно выполнять регулярно." },
    { title: "Выполняем по проверенному сценарию", description: "LocalOS проверяет данные, готовит материалы и запускает разрешённые действия по расписанию." },
    { title: "Показываем то, что требует решения", description: "Публикации, сообщения, массовые изменения и другие важные действия ждут подтверждения владельца." },
    { title: "Сохраняем результат", description: "Если способ работы подтвердил пользу, его можно повторить в этом бизнесе и использовать как обобщённую практику для других компаний." },
  ],
  workSummary: "ИИ помогает описать задачу, анализирует данные и пишет скрипт: точную последовательность действий, проверок и ограничений. Владелец проверяет сценарий и подтверждает запуск. После этого задачу выполняет скрипт — строго по утверждённым правилам, без импровизации ИИ. Если возникает ситуация, которой нет в сценарии, выполнение останавливается, а владелец получает запрос на решение. ИИ анализирует и готовит скрипт. Скрипт выполняет задачу. Владелец утверждает правила и сохраняет контроль.",
  casesEyebrow: "Кейсы",
  casesTitle: "От какой работы уже освободились владельцы",
  casesIntro: "Исходная ситуация, выполненная работа и результат за указанный период.",
  situation: "Было",
  workDone: "Сделали",
  result: "Изменилось",
  allCases: "Посмотреть все кейсы",
  auditTitle: "Снимите с себя одну задачу для начала",
  auditText: "Мы проверим карточку вашего бизнеса и покажем, что мешает клиентам найти и выбрать вас. Вы получите конкретное первое действие без большого отчёта и общих советов.",
  finalTitle: "Перестаньте быть человеком, без которого ничего не происходит",
  finalText: "Передайте LocalOS регулярную работу. Оставьте себе решения, которые действительно требуют владельца.",
  tryFree: "Посмотреть демо",
  talkExpert: "Обсудить с экспертом",
};

const enCopy: LandingCopy = {
  ...ruCopy,
  metaTitle: "LocalOS — less routine work for local business owners",
  metaDescription: "LocalOS checks listings and reviews, prepares content, analyses services and numbers, and handles recurring work. The owner steps in when a decision is needed.",
  eyebrow: "LocalOS for local businesses",
  title: "Your business needs you for decisions, not routine work",
  intro: "LocalOS watches the work owners usually keep in their heads: listings, reviews, content, services, numbers, and partnerships. The system handles recurring tasks. You step in when something needs a choice, a review, or approval.",
  seeTasks: "See what LocalOS can take over",
  freeAudit: "Choose from 6 directions",
  formTitle: "Start with a listings audit",
  formDescription: "See how customers find your business and what should be fixed first.",
  emailLabel: "Email",
  emailPlaceholder: "you@example.com",
  mapsLabel: "Business listing link",
  mapsPlaceholder: "Link to your business on maps",
  submit: "Get the audit",
  submitting: "Sending…",
  success: "Thank you. Your request has been received.",
  error: "We could not send your request. Please try again.",
  scale: "LocalOS already works across more than 240 small-business locations, from independent companies to networks.",
  problemTitle: "If everything stops without you, you are still at work after the working day ends",
  problemParagraphs: [
    "Reply to a review. Check a listing. Plan a post. Update prices. Look at the numbers. Each task is small, but together they leave the owner no time to work on the business itself.",
    "New software rarely removes this load. It usually gives the owner one more place to open and monitor.",
    "LocalOS turns recurring work into scheduled tasks, completes them, and shows the owner only what needs a decision.",
  ],
  networkTitle: "You may have one location. Your experience can work like a network's",
  networkSummary: "The same problems repeat across local businesses. LocalOS checks the solutions that worked and keeps what can be used again.",
  networkPrivacy: "Company and customer data is never passed to other businesses. Only reviewed rules and anonymised ways of working are shared.",
  networkLabels: ["One business finds a solution", "LocalOS reviews the practice", "Others do not start from zero"],
  tasksEyebrow: "Owner pain points",
  tasksTitle: "Sound familiar? LocalOS takes this work on",
  tasksIntro: "Five situations from business owners' working chats. Each one is paired with the work LocalOS handles.",
  tasks: [
    { title: "Ads are running, but bookings are still uneven", description: "LocalOS checks map listings, including services, prices, photos, posts, and reviews. It prepares corrections and proposals for local partners. External messages are sent only after your approval." },
    { title: "The day is full. A review needs an answer, and there is still nothing to post", description: "LocalOS collects unanswered reviews, prepares drafts, and schedules posts. You review what matters and approve sending." },
    { title: "There is plenty of work, but the average ticket is still low", description: "LocalOS shows which services sell and how average spend and capacity change. It prepares an upsell and cross-sell plan designed to increase the average ticket." },
    { title: "It is easier to do it myself than explain it and check it later", description: "LocalOS turns a recurring task into a procedure. You approve the rules once, then a script performs the work. If a decision is needed, the script stops." },
    { title: "Customers are there and everyone is busy, but little is left at month-end", description: "LocalOS brings revenue, expenses, average spend, and capacity together. You see how the numbers change and decide what to check first: pricing, capacity, or costs." },
  ],
  retentionNote: "When customer data is connected, LocalOS can also identify customers who have not returned and prepare an offer for a repeat visit.",
  workEyebrow: "How the work is handled",
  workTitle: "The system does the work. The owner makes the decisions",
  workIntro: "LocalOS takes recurring work off the owner's plate without taking important decisions away from them.",
  steps: [
    { title: "Connect the business", description: "LocalOS accesses only the data you choose: listings, reviews, services, financial indicators, and connected channels." },
    { title: "Find work that can leave the owner's desk", description: "The system separates a one-off problem from a task that needs to run regularly." },
    { title: "Run a reviewed procedure", description: "LocalOS checks data, prepares materials, and runs permitted actions on schedule." },
    { title: "Show what needs a decision", description: "Posts, messages, bulk changes, and other important external actions wait for the owner's approval." },
    { title: "Keep the result", description: "When a way of working proves useful, it can be repeated in the business and used as an anonymised practice for other companies." },
  ],
  workSummary: "AI is used for analysis and preparation. Recurring work follows clear rules. The owner stays in control.",
  casesEyebrow: "Case studies",
  casesTitle: "What owners have already taken off their plates",
  casesIntro: "The starting situation, the work completed, and what changed over a stated period.",
  situation: "Before",
  workDone: "Work completed",
  result: "What changed",
  allCases: "View all case studies",
  auditTitle: "Take one task off your plate first",
  auditText: "We will check your business listing and show what gets in the way of customers finding and choosing you. You will get one concrete first action, without a long report or generic advice.",
  finalTitle: "Stop being the person without whom nothing happens",
  finalText: "Give recurring work to LocalOS. Keep the decisions that genuinely need the owner.",
  tryFree: "View demo",
  talkExpert: "Talk to an expert",
};

const taskIcons = [MapPinned, MessageSquareText, CircleDollarSign, ClipboardCheck, BarChart3];
const stepIcons = [Building2, Eye, Layers3, ClipboardCheck, FileCheck2];

const compiledArticleLinkByLanguage: Record<Language, string> = {
  ru: "Почитать про технологию Compiled AI",
  en: "Read about Compiled AI",
  fr: "Découvrir la technologie Compiled AI",
  es: "Conocer la tecnología Compiled AI",
  el: "Διαβάστε για την τεχνολογία Compiled AI",
  de: "Mehr über Compiled AI erfahren",
  th: "อ่านเกี่ยวกับเทคโนโลยี Compiled AI",
  ar: "اقرأ عن تقنية Compiled AI",
  ha: "Karanta game da fasahar Compiled AI",
  tr: "Compiled AI teknolojisini okuyun",
};

const networkQuestionsByLanguage: Record<Language, NetworkQuestionSet> = {
  ru: {
    intro: "Эти вопросы владельцы снова и снова задают друг другу в рабочих чатах. Задачи повторяются — значит, найденное решение можно проверить, сохранить и использовать снова.",
    sourceNote: "Реальные вопросы из открытых отраслевых чатов. Ссылки ведут к исходным сообщениям.",
    questions: [
      { text: "Как вообще себе искать клиентов?", href: "https://t.me/beutyrussia/2486" },
      { text: "Как вы реагируете на такие отзывы?", href: "https://t.me/beutyrussia/2499" },
      { text: "Как работать с потерянными клиентами?", href: "https://t.me/salon_fm/2654" },
      { text: "Как часто вы повышаете прайс и какая цена у вас сейчас?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  en: {
    intro: "Owners ask one another these questions again and again in their work chats. The problems repeat, so a useful solution can be reviewed, saved, and used again.",
    sourceNote: "Real questions from public industry chats. Links open the original Russian messages.",
    questions: [
      { text: "How do you find customers in the first place?", href: "https://t.me/beutyrussia/2486" },
      { text: "How do you respond to reviews like these?", href: "https://t.me/beutyrussia/2499" },
      { text: "How do you work with customers who stopped coming?", href: "https://t.me/salon_fm/2654" },
      { text: "How often do you raise prices, and what do you charge now?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  fr: {
    intro: "Les propriétaires se posent régulièrement les mêmes questions dans leurs groupes de travail. Les problèmes se répètent : une solution utile peut donc être vérifiée, conservée et réutilisée.",
    sourceNote: "Questions réelles issues de groupes professionnels publics. Les liens ouvrent les messages russes d’origine.",
    questions: [
      { text: "Comment trouver ses premiers clients ?", href: "https://t.me/beutyrussia/2486" },
      { text: "Comment réagissez-vous à ce type d’avis ?", href: "https://t.me/beutyrussia/2499" },
      { text: "Comment travailler avec les clients qui ne reviennent plus ?", href: "https://t.me/salon_fm/2654" },
      { text: "À quelle fréquence augmentez-vous vos prix ?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  es: {
    intro: "Los propietarios se hacen estas preguntas una y otra vez en sus grupos de trabajo. Los problemas se repiten, así que una solución útil puede revisarse, guardarse y volver a utilizarse.",
    sourceNote: "Preguntas reales de chats públicos del sector. Los enlaces abren los mensajes originales en ruso.",
    questions: [
      { text: "¿Cómo encontrar clientes desde el principio?", href: "https://t.me/beutyrussia/2486" },
      { text: "¿Cómo respondes a reseñas como estas?", href: "https://t.me/beutyrussia/2499" },
      { text: "¿Cómo trabajar con clientes que dejaron de venir?", href: "https://t.me/salon_fm/2654" },
      { text: "¿Con qué frecuencia subes los precios?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  el: {
    intro: "Οι ιδιοκτήτες κάνουν ξανά και ξανά αυτές τις ερωτήσεις στις επαγγελματικές συνομιλίες τους. Τα προβλήματα επαναλαμβάνονται, άρα μια χρήσιμη λύση μπορεί να ελεγχθεί, να αποθηκευτεί και να χρησιμοποιηθεί ξανά.",
    sourceNote: "Πραγματικές ερωτήσεις από δημόσιες επαγγελματικές συνομιλίες. Οι σύνδεσμοι ανοίγουν τα αρχικά ρωσικά μηνύματα.",
    questions: [
      { text: "Πώς βρίσκετε πελάτες από την αρχή;", href: "https://t.me/beutyrussia/2486" },
      { text: "Πώς απαντάτε σε τέτοιες κριτικές;", href: "https://t.me/beutyrussia/2499" },
      { text: "Πώς προσεγγίζετε πελάτες που σταμάτησαν να έρχονται;", href: "https://t.me/salon_fm/2654" },
      { text: "Πόσο συχνά αυξάνετε τις τιμές σας;", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  de: {
    intro: "In ihren Arbeitschats stellen Inhaber einander immer wieder dieselben Fragen. Die Aufgaben wiederholen sich – deshalb lässt sich eine hilfreiche Lösung prüfen, speichern und erneut einsetzen.",
    sourceNote: "Echte Fragen aus öffentlichen Branchenchats. Die Links öffnen die russischen Originalbeiträge.",
    questions: [
      { text: "Wie findet man überhaupt neue Kunden?", href: "https://t.me/beutyrussia/2486" },
      { text: "Wie reagieren Sie auf solche Bewertungen?", href: "https://t.me/beutyrussia/2499" },
      { text: "Wie gewinnt man Kunden zurück, die nicht mehr kommen?", href: "https://t.me/salon_fm/2654" },
      { text: "Wie oft erhöhen Sie Ihre Preise?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  th: {
    intro: "เจ้าของธุรกิจถามคำถามเหล่านี้ซ้ำ ๆ ในกลุ่มสนทนาเรื่องงาน ปัญหาเดิมเกิดขึ้นกับหลายคน จึงสามารถตรวจสอบ เก็บ และนำวิธีที่ได้ผลกลับมาใช้ได้อีก",
    sourceNote: "คำถามจริงจากกลุ่มสนทนาสาธารณะในอุตสาหกรรม ลิงก์จะเปิดข้อความต้นฉบับภาษารัสเซีย",
    questions: [
      { text: "เริ่มหาลูกค้าได้อย่างไร?", href: "https://t.me/beutyrussia/2486" },
      { text: "คุณตอบรีวิวแบบนี้อย่างไร?", href: "https://t.me/beutyrussia/2499" },
      { text: "จะดูแลลูกค้าที่เลิกมาใช้บริการอย่างไร?", href: "https://t.me/salon_fm/2654" },
      { text: "คุณปรับราคาบ่อยแค่ไหน?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  ar: {
    intro: "يطرح أصحاب الأعمال هذه الأسئلة على بعضهم مرارًا في محادثات العمل. تتكرر المشكلات، لذلك يمكن مراجعة الحل المفيد وحفظه واستخدامه مرة أخرى.",
    sourceNote: "أسئلة حقيقية من محادثات عامة متخصصة. تفتح الروابط الرسائل الروسية الأصلية.",
    questions: [
      { text: "كيف تجد العملاء من الأساس؟", href: "https://t.me/beutyrussia/2486" },
      { text: "كيف ترد على مراجعات كهذه؟", href: "https://t.me/beutyrussia/2499" },
      { text: "كيف تتعامل مع العملاء الذين توقفوا عن العودة؟", href: "https://t.me/salon_fm/2654" },
      { text: "كم مرة ترفع أسعارك؟", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  ha: {
    intro: "Masu kasuwanci suna maimaita waɗannan tambayoyi a tattaunawar aikinsu. Matsalolin suna dawowa, don haka ana iya bincika mafita mai amfani, a adana ta, sannan a sake amfani da ita.",
    sourceNote: "Tambayoyi na gaske daga tattaunawar sana’a ta jama’a. Hanyoyin suna buɗe saƙonnin asali na Rashanci.",
    questions: [
      { text: "Ta yaya ake fara samun kwastomomi?", href: "https://t.me/beutyrussia/2486" },
      { text: "Ta yaya kuke amsa irin waɗannan ra’ayoyi?", href: "https://t.me/beutyrussia/2499" },
      { text: "Ta yaya ake dawo da kwastomomin da suka daina zuwa?", href: "https://t.me/salon_fm/2654" },
      { text: "Sau nawa kuke ƙara farashi?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
  tr: {
    intro: "İşletme sahipleri çalışma sohbetlerinde bu soruları tekrar tekrar birbirlerine soruyor. Sorunlar tekrarlandığı için yararlı bir çözüm incelenebilir, saklanabilir ve yeniden kullanılabilir.",
    sourceNote: "Herkese açık sektör sohbetlerinden gerçek sorular. Bağlantılar Rusça özgün mesajları açar.",
    questions: [
      { text: "En başta müşteri nasıl bulunur?", href: "https://t.me/beutyrussia/2486" },
      { text: "Böyle yorumlara nasıl yanıt veriyorsunuz?", href: "https://t.me/beutyrussia/2499" },
      { text: "Artık gelmeyen müşterilerle nasıl çalışılır?", href: "https://t.me/salon_fm/2654" },
      { text: "Fiyatlarınızı ne sıklıkla artırıyorsunuz?", href: "https://t.me/beutyrussia/2702" },
    ],
  },
};

const productPreviewByLanguage: Record<Language, ProductPreviewCopy> = {
  ru: {
    eyebrow: "Сегодня в LocalOS",
    title: "Работа идёт без напоминаний",
    active: "Система работает",
    items: [
      { title: "Карточки на картах", detail: "Проверены услуги, цены и отзывы", status: "Проверено" },
      { title: "Отзывы без ответа", detail: "Черновики собраны в очередь", status: "Подготовлено" },
      { title: "Публикация на неделю", detail: "Текст готов к вашему решению", status: "Подтвердить" },
    ],
    ownerNote: "Вы подключаетесь только там, где нужно решение.",
  },
  en: {
    eyebrow: "Today in LocalOS",
    title: "Work continues without reminders",
    active: "System running",
    items: [
      { title: "Map listings", detail: "Services, prices, and reviews checked", status: "Checked" },
      { title: "Unanswered reviews", detail: "Drafts added to the queue", status: "Prepared" },
      { title: "Weekly post", detail: "Copy is ready for your decision", status: "Approve" },
    ],
    ownerNote: "You step in only when a decision is needed.",
  },
  fr: {
    eyebrow: "Aujourd’hui dans LocalOS",
    title: "Le travail avance sans rappel",
    active: "Système actif",
    items: [
      { title: "Fiches sur les cartes", detail: "Services, prix et avis vérifiés", status: "Vérifié" },
      { title: "Avis sans réponse", detail: "Brouillons ajoutés à la file", status: "Préparé" },
      { title: "Publication de la semaine", detail: "Texte prêt pour votre décision", status: "Approuver" },
    ],
    ownerNote: "Vous intervenez uniquement lorsqu’une décision est nécessaire.",
  },
  es: {
    eyebrow: "Hoy en LocalOS",
    title: "El trabajo continúa sin recordatorios",
    active: "Sistema activo",
    items: [
      { title: "Fichas en mapas", detail: "Servicios, precios y reseñas revisados", status: "Revisado" },
      { title: "Reseñas sin respuesta", detail: "Borradores añadidos a la cola", status: "Preparado" },
      { title: "Publicación semanal", detail: "Texto listo para tu decisión", status: "Aprobar" },
    ],
    ownerNote: "Solo intervienes cuando hace falta una decisión.",
  },
  el: {
    eyebrow: "Σήμερα στο LocalOS",
    title: "Η δουλειά προχωρά χωρίς υπενθυμίσεις",
    active: "Το σύστημα λειτουργεί",
    items: [
      { title: "Καταχωρίσεις στους χάρτες", detail: "Ελέγχθηκαν υπηρεσίες, τιμές και κριτικές", status: "Ελέγχθηκε" },
      { title: "Κριτικές χωρίς απάντηση", detail: "Τα προσχέδια μπήκαν στη σειρά", status: "Έτοιμο" },
      { title: "Εβδομαδιαία δημοσίευση", detail: "Το κείμενο περιμένει την απόφασή σας", status: "Έγκριση" },
    ],
    ownerNote: "Συμμετέχετε μόνο όταν χρειάζεται απόφαση.",
  },
  de: {
    eyebrow: "Heute in LocalOS",
    title: "Die Arbeit läuft ohne Erinnerungen weiter",
    active: "System läuft",
    items: [
      { title: "Karteneinträge", detail: "Leistungen, Preise und Bewertungen geprüft", status: "Geprüft" },
      { title: "Unbeantwortete Bewertungen", detail: "Entwürfe zur Warteschlange hinzugefügt", status: "Vorbereitet" },
      { title: "Wochenbeitrag", detail: "Text wartet auf Ihre Entscheidung", status: "Freigeben" },
    ],
    ownerNote: "Sie greifen nur ein, wenn eine Entscheidung nötig ist.",
  },
  th: {
    eyebrow: "วันนี้ใน LocalOS",
    title: "งานเดินหน้าต่อโดยไม่ต้องคอยเตือน",
    active: "ระบบกำลังทำงาน",
    items: [
      { title: "ข้อมูลบนแผนที่", detail: "ตรวจบริการ ราคา และรีวิวแล้ว", status: "ตรวจแล้ว" },
      { title: "รีวิวที่ยังไม่ได้ตอบ", detail: "เตรียมร่างไว้ในคิวแล้ว", status: "เตรียมแล้ว" },
      { title: "โพสต์ประจำสัปดาห์", detail: "ข้อความพร้อมให้คุณตัดสินใจ", status: "อนุมัติ" },
    ],
    ownerNote: "คุณเข้ามาเฉพาะเมื่อจำเป็นต้องตัดสินใจ",
  },
  ar: {
    eyebrow: "اليوم في LocalOS",
    title: "يستمر العمل من دون تذكير",
    active: "النظام يعمل",
    items: [
      { title: "بطاقات الخرائط", detail: "تم فحص الخدمات والأسعار والمراجعات", status: "تم الفحص" },
      { title: "مراجعات بلا رد", detail: "أضيفت المسودات إلى قائمة الانتظار", status: "جاهز" },
      { title: "منشور الأسبوع", detail: "النص جاهز لقرارك", status: "موافقة" },
    ],
    ownerNote: "تتدخل فقط عندما يلزم اتخاذ قرار.",
  },
  ha: {
    eyebrow: "Yau a LocalOS",
    title: "Aiki yana ci gaba ba tare da tunatarwa ba",
    active: "Tsarin yana aiki",
    items: [
      { title: "Bayanan taswira", detail: "An duba ayyuka, farashi da ra’ayoyi", status: "An duba" },
      { title: "Ra’ayoyin da ba a amsa ba", detail: "An shirya rubutun amsa", status: "An shirya" },
      { title: "Rubutun mako", detail: "Rubutun yana jiran shawarar ku", status: "Amince" },
    ],
    ownerNote: "Kuna shiga ne kawai idan ana buƙatar shawara.",
  },
  tr: {
    eyebrow: "Bugün LocalOS’ta",
    title: "İş, hatırlatma olmadan ilerliyor",
    active: "Sistem çalışıyor",
    items: [
      { title: "Harita kayıtları", detail: "Hizmetler, fiyatlar ve yorumlar kontrol edildi", status: "Kontrol edildi" },
      { title: "Yanıtsız yorumlar", detail: "Taslaklar sıraya eklendi", status: "Hazırlandı" },
      { title: "Haftalık gönderi", detail: "Metin kararınızı bekliyor", status: "Onayla" },
    ],
    ownerNote: "Yalnızca karar gerektiğinde devreye girersiniz.",
  },
};

const copyForLanguage = (language: Language): LandingCopy => {
  switch (language) {
    case "ru":
      return ruCopy;
    case "en":
      return enCopy;
    case "fr":
      return landingTranslations.fr;
    case "es":
      return landingTranslations.es;
    case "el":
      return landingTranslations.el;
    case "de":
      return landingTranslations.de;
    case "th":
      return landingTranslations.th;
    case "ar":
      return landingTranslations.ar;
    case "ha":
      return landingTranslations.ha;
    case "tr":
      return landingTranslations.tr;
  }
};

const Index = () => {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { language } = useLanguage();
  const { cases: localizedCases, isLoading: casesLoading } = useLocalizedCases(language);
  const location = useLocation();
  const copy = copyForLanguage(language);
  const networkQuestions = networkQuestionsByLanguage[language];
  const productPreview = productPreviewByLanguage[language];
  const compiledArticleLink = compiledArticleLinkByLanguage[language];

  useEffect(() => {
    if (!["#agents", "#cta", "#hero-form"].includes(location.hash)) return;
    const element = document.getElementById(location.hash.slice(1));
    if (!element) return;
    const timeoutId = window.setTimeout(() => element.scrollIntoView({ behavior: "smooth" }), 100);
    return () => window.clearTimeout(timeoutId);
  }, [location.hash]);

  const scrollToAudit = () => {
    const form = document.getElementById("hero-form");
    form?.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => form?.querySelector<HTMLInputElement>("input")?.focus(), 450);
  };

  return (
    <div className="min-h-screen overflow-hidden bg-[#f7f7f5] text-slate-950 selection:bg-orange-200 selection:text-slate-950">
      <SeoMeta
        description={copy.metaDescription}
        image="/images/articles/pochemu-predprinimateli-vygorayut-cover.png"
        path="/"
        title={copy.metaTitle}
      />

      <main>
        <section className="relative isolate px-4 pb-12 pt-12 sm:px-6 sm:pb-16 sm:pt-16 lg:px-8 lg:pb-20 lg:pt-20">
          <PublicBrandBackdrop />
          <div className="mx-auto grid max-w-7xl items-start gap-12 lg:grid-cols-[minmax(0,0.95fr)_minmax(440px,1.05fr)] lg:gap-16">
            <div className="pt-4 lg:sticky lg:top-28 lg:pt-10">
              <div className="inline-flex min-h-10 items-center gap-2 rounded-full bg-white/75 px-4 py-2 text-sm font-semibold text-orange-700 shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_1px_2px_rgba(0,0,0,0.04)] backdrop-blur">
                <Sparkles className="h-4 w-4 text-orange-500" aria-hidden="true" />
                {copy.eyebrow}
              </div>
              <h1 className="mt-7 max-w-3xl text-balance text-[2.75rem] font-bold leading-[0.98] tracking-[-0.055em] text-slate-950 sm:text-6xl lg:text-[4.75rem]">
                {copy.title}
              </h1>
              <p className="mt-7 max-w-2xl text-pretty text-lg leading-8 text-slate-600 sm:text-xl sm:leading-9">{copy.intro}</p>
              <div className="mt-9 grid w-full gap-3 sm:grid-cols-[minmax(0,0.9fr)_minmax(0,1.2fr)]">
                <Button asChild className="btn-iridescent h-auto min-h-20 w-full justify-between gap-4 whitespace-normal rounded-xl px-6 py-4 text-left text-base leading-6">
                  <Link to="/growth">{copy.freeAudit}<ArrowRight className="h-5 w-5 shrink-0" aria-hidden="true" /></Link>
                </Button>
                <Link className="group inline-flex min-h-20 w-full items-center justify-between gap-4 whitespace-normal rounded-xl bg-slate-950 px-6 py-4 text-left text-base font-semibold leading-6 text-white transition-[background-color,scale] hover:bg-slate-800 active:scale-[0.96]" to={{ pathname: "/", hash: "#agents" }}>
                  {copy.seeTasks}
                  <ArrowRight className="h-4 w-4 shrink-0 transition-transform group-hover:translate-x-1" aria-hidden="true" />
                </Link>
              </div>
              <div className="mt-10 flex items-start gap-3 border-l-2 border-orange-300 pl-4 text-sm leading-6 text-slate-600">
                <Users className="mt-0.5 h-4 w-4 shrink-0 text-orange-600" aria-hidden="true" />
                <p className="max-w-xl">{copy.scale}</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-[1.75rem] bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_24px_70px_rgba(15,23,42,0.12)]">
              <div className="bg-slate-950 p-5 text-white sm:p-7">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-orange-400">{productPreview.eyebrow}</p>
                    <h2 className="mt-2 text-balance text-2xl font-bold tracking-[-0.025em] sm:text-3xl">{productPreview.title}</h2>
                  </div>
                  <div className="inline-flex min-h-9 items-center gap-2 rounded-full bg-emerald-400/10 px-3 text-xs font-semibold text-emerald-300 shadow-[inset_0_0_0_1px_rgba(110,231,183,0.16)]">
                    <span className="relative flex h-2 w-2" aria-hidden="true">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60 motion-reduce:animate-none" />
                      <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                    </span>
                    {productPreview.active}
                  </div>
                </div>
                <div className="mt-7 overflow-hidden rounded-2xl bg-white/[0.055] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]">
                  {productPreview.items.map((item, index) => {
                    const Icon = index === 0 ? CircleCheck : index === 1 ? Clock3 : CalendarClock;
                    return (
                      <div className={`grid gap-3 p-4 sm:grid-cols-[auto_1fr_auto] sm:items-center ${index > 0 ? "border-t border-white/[0.08]" : ""}`} key={item.title}>
                        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${index === 2 ? "bg-orange-400/12 text-orange-300" : "bg-emerald-400/10 text-emerald-300"}`}>
                          <Icon className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <div>
                          <h3 className="text-pretty text-sm font-semibold text-white sm:text-base">{item.title}</h3>
                          <p className="mt-1 text-pretty text-xs leading-5 text-slate-400 sm:text-sm">{item.detail}</p>
                        </div>
                        <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${index === 2 ? "bg-orange-400/12 text-orange-300" : "bg-white/[0.06] text-slate-300"}`}>{item.status}</span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-5 flex items-center gap-2 text-pretty text-sm leading-6 text-slate-300">
                  <Eye className="h-4 w-4 shrink-0 text-orange-400" aria-hidden="true" />
                  {productPreview.ownerNote}
                </p>
              </div>

              <div className="p-5 sm:p-7">
                <div className="flex items-start gap-4">
                  <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-orange-100 text-orange-700">
                    <MapPinned className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold tracking-tight text-slate-950 sm:text-2xl">{copy.formTitle}</h2>
                    <p className="mt-2 text-pretty text-sm leading-6 text-slate-600">{copy.formDescription}</p>
                  </div>
                </div>
                <form
                  className="mt-6 grid gap-4"
                  id="hero-form"
                  onSubmit={async (event) => {
                    event.preventDefault();
                    if (isSubmitting) return;
                    setIsSubmitting(true);
                    const form = event.currentTarget;
                    const emailInput = form.elements.namedItem("email");
                    const mapsInput = form.elements.namedItem("yandexUrl");
                    if (!(emailInput instanceof HTMLInputElement) || !(mapsInput instanceof HTMLInputElement)) {
                      setIsSubmitting(false);
                      return;
                    }
                    try {
                      const response = await fetch("/api/public/request-report", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: emailInput.value, url: mapsInput.value }),
                      });
                      const result: unknown = await response.json().catch(() => null);
                      const payload = result && typeof result === "object" ? result : null;
                      const errorMessage = payload && "error" in payload && typeof payload.error === "string"
                        ? payload.error
                        : payload && "message" in payload && typeof payload.message === "string"
                          ? payload.message
                          : copy.error;
                      if (!response.ok) throw new Error(errorMessage);
                      const publicUrl = payload && "public_url" in payload && typeof payload.public_url === "string"
                        ? payload.public_url.trim()
                        : "";
                      if (publicUrl) {
                        window.location.href = publicUrl;
                        return;
                      }
                      form.reset();
                      window.alert(copy.success);
                    } catch (error) {
                      window.alert(error instanceof Error ? error.message : copy.error);
                    } finally {
                      setIsSubmitting(false);
                    }
                  }}
                >
                  <label className="block">
                    <span className="mb-2 block text-sm font-semibold text-slate-700">{copy.emailLabel}</span>
                    <input className="min-h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-slate-950 outline-none transition-[border-color,box-shadow] placeholder:text-slate-400 focus:border-orange-400 focus:ring-4 focus:ring-orange-100" name="email" placeholder={copy.emailPlaceholder} required type="email" />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-sm font-semibold text-slate-700">{copy.mapsLabel}</span>
                    <input className="min-h-12 w-full rounded-xl border border-slate-200 bg-white px-4 text-slate-950 outline-none transition-[border-color,box-shadow] placeholder:text-slate-400 focus:border-orange-400 focus:ring-4 focus:ring-orange-100" name="yandexUrl" placeholder={copy.mapsPlaceholder} required type="url" />
                  </label>
                  <Button className="btn-iridescent min-h-12 w-full rounded-xl text-base" disabled={isSubmitting} type="submit">
                    {isSubmitting ? <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : <ArrowRight className="h-5 w-5" aria-hidden="true" />}
                    <span>{isSubmitting ? copy.submitting : copy.submit}</span>
                  </Button>
                </form>
              </div>
            </div>
          </div>
        </section>

        <section className="px-4 py-16 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <div className="mx-auto grid max-w-7xl overflow-hidden rounded-[1.75rem] bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_16px_45px_rgba(15,23,42,0.06)] lg:grid-cols-[0.82fr_1.18fr]">
            <div className="relative overflow-hidden bg-slate-950 p-7 text-white sm:p-10 lg:p-12">
              <div className="absolute -right-16 -top-16 h-44 w-44 rounded-full bg-orange-500/15 blur-3xl" aria-hidden="true" />
              <span className="text-sm font-bold uppercase tracking-[0.18em] text-orange-400">01</span>
              <h2 className="mt-5 max-w-xl text-balance text-3xl font-bold tracking-[-0.035em] sm:text-4xl lg:text-5xl">{copy.problemTitle}</h2>
              <div className="mt-10 hidden items-center gap-3 text-sm text-slate-400 lg:flex">
                <span className="h-px w-10 bg-orange-400" aria-hidden="true" />
                LocalOS
              </div>
            </div>
            <div className="grid gap-px bg-slate-200/70 sm:grid-cols-2">
              {copy.problemParagraphs.map((paragraph, index) => (
                <div className={`bg-white p-7 sm:p-8 ${index === copy.problemParagraphs.length - 1 ? "sm:col-span-2 sm:grid sm:grid-cols-[auto_1fr] sm:items-start sm:gap-5" : ""}`} key={paragraph}>
                  <span className={`mb-5 flex h-9 w-9 items-center justify-center rounded-full text-sm font-bold tabular-nums ${index === copy.problemParagraphs.length - 1 ? "bg-orange-500 text-white" : "bg-slate-100 text-slate-500"}`}>0{index + 1}</span>
                  <p className={`text-pretty leading-7 ${index === copy.problemParagraphs.length - 1 ? "text-lg font-semibold text-slate-950 sm:pt-1" : "text-base text-slate-600"}`}>{paragraph}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="bg-[#ece9e2] px-4 py-16 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-7xl">
            <div className="grid gap-7 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.62fr)] lg:items-end lg:gap-20">
              <div>
                <span className="text-sm font-bold uppercase tracking-[0.18em] text-orange-700">02</span>
                <h2 className="mt-5 max-w-3xl text-balance text-3xl font-bold tracking-[-0.04em] text-slate-950 sm:text-4xl lg:text-5xl">{copy.networkTitle}</h2>
              </div>
              <p className="max-w-xl border-l-2 border-orange-500 pl-5 text-pretty text-lg leading-8 text-slate-600">{copy.networkSummary}</p>
            </div>

            <div className="mt-12 grid overflow-hidden rounded-[1.75rem] bg-slate-950 shadow-[0_24px_70px_rgba(15,23,42,0.16)] lg:grid-cols-[1.05fr_0.95fr]">
              <div className="p-6 text-white sm:p-8 lg:p-10">
                <p className="max-w-2xl text-pretty text-lg font-semibold leading-8 text-slate-100">{networkQuestions.intro}</p>
                <ul className="mt-7 grid gap-2.5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
                  {networkQuestions.questions.map((question) => (
                    <li key={question.href}>
                      <a
                        aria-label={`${question.text} — ${networkQuestions.sourceNote}`}
                        className="group flex h-full min-h-14 items-center justify-between gap-4 rounded-xl bg-white/[0.055] px-4 py-3 text-sm font-semibold leading-6 text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)] transition-[background-color,box-shadow,scale] hover:bg-white/[0.09] hover:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.14)] active:scale-[0.96]"
                        href={question.href}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <span className="text-pretty">«{question.text}»</span>
                        <ArrowUpRight className="h-4 w-4 shrink-0 text-orange-400 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" />
                      </a>
                    </li>
                  ))}
                </ul>
                <p className="mt-4 text-pretty text-xs leading-5 text-slate-500">{networkQuestions.sourceNote}</p>
              </div>

              <div className="bg-white p-6 sm:p-8 lg:p-10">
                <ol className="relative">
                  <span className="absolute bottom-8 left-[1.15rem] top-8 w-px bg-slate-200" aria-hidden="true" />
                  {copy.networkLabels.map((label, index) => {
                    const Icon = index === 0 ? Building2 : index === 1 ? ShieldCheck : Network;
                    return (
                      <li className={`relative grid grid-cols-[2.4rem_1fr] gap-4 ${index > 0 ? "mt-7" : ""}`} key={label}>
                        <div className={`relative z-10 flex h-10 w-10 items-center justify-center rounded-xl ${index === copy.networkLabels.length - 1 ? "bg-orange-500 text-white" : "bg-slate-100 text-slate-600"}`}>
                          <Icon className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <div className="pt-1">
                          <span className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400 tabular-nums">0{index + 1}</span>
                          <p className="mt-1 text-pretty text-lg font-bold leading-7 text-slate-950">{label}</p>
                        </div>
                      </li>
                    );
                  })}
                </ol>
                <div className="mt-9 flex gap-3 border-t border-slate-200 pt-6 text-sm leading-6 text-slate-600">
                  <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-orange-600" aria-hidden="true" />
                  <p className="text-pretty">{copy.networkPrivacy}</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="scroll-mt-24 px-4 py-16 sm:px-6 sm:py-20 lg:px-8 lg:py-24" id="agents">
          <div className="mx-auto max-w-7xl">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(22rem,0.62fr)] lg:items-end lg:gap-20">
              <div>
                <span className="text-sm font-bold uppercase tracking-[0.18em] text-orange-700">{copy.tasksEyebrow}</span>
                <h2 className="mt-5 max-w-3xl text-balance text-3xl font-bold tracking-[-0.04em] sm:text-4xl lg:text-5xl">{copy.tasksTitle}</h2>
              </div>
              <p className="max-w-2xl text-pretty text-lg leading-8 text-slate-600 lg:justify-self-end">{copy.tasksIntro}</p>
            </div>
            <div className="mt-10 grid gap-5 md:grid-cols-2 lg:grid-cols-6">
              {copy.tasks.map((task, index) => {
                const Icon = taskIcons[index];
                return (
                  <article className={`relative flex flex-col overflow-hidden rounded-[1.25rem] bg-white text-slate-950 shadow-[0_0_0_1px_rgba(0,0,0,0.055),0_8px_24px_rgba(15,23,42,0.045)] ${index < 3 ? "lg:col-span-2" : "lg:col-span-3"}`} key={task.title}>
                    <div className="flex flex-1 flex-col p-6 sm:p-7">
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                          <Icon className="h-5 w-5" aria-hidden="true" />
                        </div>
                        <span className="text-sm font-bold text-slate-300 tabular-nums">0{index + 1}</span>
                      </div>
                      <div className="mt-6 h-0.5 w-8 rounded-full bg-orange-500" aria-hidden="true" />
                      <h3 className="mt-5 text-pretty text-xl font-bold leading-7">{task.title}</h3>
                    </div>
                    <div className="border-t border-orange-100 bg-[#fffaf5] p-6 sm:p-7">
                      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-orange-700">
                        <CircleCheck className="h-4 w-4" aria-hidden="true" />
                        LocalOS
                      </div>
                      <p className="mt-3 text-pretty leading-7 text-slate-700">{task.description}</p>
                    </div>
                  </article>
                );
              })}
            </div>
            <div className="mt-6 flex max-w-4xl gap-3 border-l-2 border-orange-400 py-1 pl-4 text-sm leading-6 text-slate-600">
              <Check className="mt-0.5 h-5 w-5 shrink-0 text-orange-600" aria-hidden="true" />
              <p className="text-pretty">{copy.retentionNote}</p>
            </div>
          </div>
        </section>

        <section className="relative overflow-hidden bg-slate-950 px-4 py-16 text-white sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <div className="pointer-events-none absolute -left-32 top-1/3 h-80 w-80 rounded-full bg-orange-500/10 blur-3xl" aria-hidden="true" />
          <div className="mx-auto grid max-w-7xl gap-12 lg:grid-cols-[0.78fr_1.22fr] lg:gap-20">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <span className="text-sm font-bold uppercase tracking-[0.18em] text-orange-400">{copy.workEyebrow}</span>
              <h2 className="mt-5 max-w-xl text-balance text-3xl font-bold tracking-[-0.04em] sm:text-4xl lg:text-5xl">{copy.workTitle}</h2>
              <p className="mt-6 max-w-xl text-pretty text-lg leading-8 text-slate-300">{copy.workIntro}</p>
              <div className="mt-9 rounded-2xl bg-orange-500/10 p-5 shadow-[inset_0_0_0_1px_rgba(251,146,60,0.18)]">
                <p className="text-pretty text-sm font-semibold leading-6 text-orange-100">{copy.workSummary}</p>
                <Link
                  className="mt-5 inline-flex min-h-11 items-center gap-2 border-t border-orange-300/20 pt-4 text-sm font-bold text-orange-300 transition-colors hover:text-orange-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950"
                  to="/articles/compiled-ai-pochemu-ii-dolzhen-dumat-odin-raz"
                >
                  {compiledArticleLink}
                  <ArrowUpRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                </Link>
              </div>
            </div>

            <ol className="overflow-hidden rounded-[1.5rem] bg-white/[0.045] shadow-[inset_0_0_0_1px_rgba(255,255,255,0.08)]">
              {copy.steps.map((step, index) => {
                const Icon = stepIcons[index];
                return (
                  <li className={`group grid gap-4 p-5 transition-[background-color] hover:bg-white/[0.035] sm:grid-cols-[3rem_1fr_auto] sm:items-start sm:p-6 ${index > 0 ? "border-t border-white/[0.08]" : ""}`} key={step.title}>
                    <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${index === copy.steps.length - 1 ? "bg-orange-500 text-white" : "bg-white/[0.07] text-orange-300"}`}>
                      <Icon className="h-5 w-5" aria-hidden="true" />
                    </div>
                    <div>
                      <h3 className="text-pretty text-lg font-bold leading-7 text-white">{step.title}</h3>
                      <p className="mt-2 max-w-2xl text-pretty text-sm leading-6 text-slate-400 sm:text-base">{step.description}</p>
                    </div>
                    <span className="tabular-nums text-sm font-bold text-slate-600">0{index + 1}</span>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>

        <section className="bg-white px-4 py-16 sm:px-6 sm:py-20 lg:px-8 lg:py-24">
          <div className="mx-auto max-w-7xl">
            <div>
              <span className="text-sm font-bold uppercase tracking-[0.18em] text-orange-700">{copy.casesEyebrow}</span>
              <h2 className="mt-5 max-w-3xl text-balance text-3xl font-bold tracking-[-0.04em] sm:text-4xl lg:text-5xl">{copy.casesTitle}</h2>
            </div>
            <div className="mt-10 grid gap-5 lg:grid-cols-3">
              {casesLoading
                ? Array.from({ length: 3 }, (_, index) => (
                    <div className="h-[41rem] animate-pulse rounded-2xl bg-slate-100" key={index} aria-hidden="true" />
                  ))
                : localizedCases.slice(0, 3).map((caseItem) => (
                <article className="group flex h-full flex-col overflow-hidden rounded-2xl bg-[#f7f7f5] shadow-[0_0_0_1px_rgba(0,0,0,0.055),0_8px_24px_rgba(15,23,42,0.045)] transition-[box-shadow,transform] hover:-translate-y-1 hover:shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_18px_42px_rgba(15,23,42,0.09)]" key={caseItem.slug}>
                  <div className="p-6 pb-5">
                    <div className="flex items-start justify-between gap-4">
                      <span className="text-xs font-bold uppercase tracking-[0.14em] text-orange-700">{copy.casesEyebrow}</span>
                      <ArrowUpRight className="h-5 w-5 text-slate-300 transition-[color,transform] group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-orange-600" aria-hidden="true" />
                    </div>
                    <h3 className="mt-5 min-h-16 text-balance text-2xl font-bold leading-8 text-slate-950">{caseItem.title}</h3>
                  </div>
                  <div className="grid grid-cols-1 gap-px bg-slate-200/80 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                    {caseItem.metrics.map((metric) => (
                      <div className="bg-white px-4 py-3" key={metric.label}>
                        <strong className="block text-lg font-bold text-orange-600 tabular-nums">{metric.value}</strong>
                        <span className="mt-0.5 block text-pretty text-xs leading-5 text-slate-500">{metric.label}</span>
                      </div>
                    ))}
                  </div>
                  <dl className="flex flex-1 flex-col p-6 pt-5 text-sm leading-6">
                    <div className="lg:min-h-[8.5rem]">
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.situation}</dt>
                      <dd className="mt-1 text-pretty text-slate-600">{caseItem.situation}</dd>
                    </div>
                    <div className="mt-5 lg:min-h-[10rem]">
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.workDone}</dt>
                      <dd className="mt-2">
                        <ul className="space-y-2 text-slate-600">
                          {caseItem.actions.slice(0, 2).map((action) => <li className="flex gap-2 text-pretty" key={action}><Check className="mt-1 h-4 w-4 shrink-0 text-orange-500" aria-hidden="true" />{action}</li>)}
                        </ul>
                      </dd>
                    </div>
                    <div className="mt-5 border-t border-slate-200 pt-5">
                      <dt className="font-bold uppercase tracking-[0.1em] text-slate-400">{copy.result}</dt>
                      <dd className="mt-1 text-pretty font-semibold text-slate-800">{caseItem.result}</dd>
                    </div>
                  </dl>
                  <Link className="mx-6 mb-6 mt-auto inline-flex min-h-11 items-center gap-2 text-pretty font-semibold leading-6 text-orange-600 transition-colors hover:text-orange-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange-500 focus-visible:ring-offset-2" to={`/cases/${caseItem.slug}`}>
                    {caseItem.title}<ArrowRight className="h-4 w-4 shrink-0" aria-hidden="true" />
                  </Link>
                </article>
                  ))}
            </div>
            <Button asChild className="mt-8 min-h-12 rounded-xl px-6 transition-[box-shadow,scale] active:scale-[0.96]" variant="outline">
              <Link to="/cases">{copy.allCases}<ArrowRight className="h-4 w-4" aria-hidden="true" /></Link>
            </Button>
          </div>
        </section>

        <section className="bg-white px-4 pb-16 sm:px-6 sm:pb-20 lg:px-8 lg:pb-24">
          <div className="mx-auto flex max-w-7xl flex-col items-start justify-between gap-7 rounded-[1.75rem] bg-[#ece9e2] p-7 sm:p-10 lg:flex-row lg:items-center lg:p-12">
            <div className="max-w-3xl">
              <h2 className="text-balance text-3xl font-bold tracking-[-0.035em] sm:text-4xl">{copy.auditTitle}</h2>
              <p className="mt-4 text-pretty text-lg leading-8 text-slate-600">{copy.auditText}</p>
            </div>
            <Button className="btn-iridescent min-h-12 shrink-0 rounded-xl px-6" onClick={scrollToAudit} size="lg">
              {copy.submit}<ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Button>
          </div>
        </section>

        <section className="relative overflow-hidden bg-slate-950 px-4 py-20 text-white sm:px-6 lg:px-8 lg:py-28" id="cta">
          <div className="pointer-events-none absolute left-1/2 top-0 h-96 w-96 -translate-x-1/2 rounded-full bg-orange-500/14 blur-3xl" aria-hidden="true" />
          <div className="relative mx-auto max-w-5xl text-center">
            <h2 className="text-balance text-3xl font-bold tracking-[-0.04em] sm:text-4xl lg:text-6xl">{copy.finalTitle}</h2>
            <p className="mx-auto mt-6 max-w-3xl text-pretty text-lg leading-8 text-slate-300 sm:text-xl">{copy.finalText}</p>
            <div className="mt-9 flex flex-col justify-center gap-3 sm:flex-row">
              <Button asChild className="btn-iridescent min-h-12 rounded-xl px-7 text-base" size="lg">
                <a href="/demo" rel="noopener noreferrer" target="_blank">{copy.tryFree}<ArrowRight className="h-5 w-5" aria-hidden="true" /></a>
              </Button>
              <Button asChild className="min-h-12 rounded-xl border-white/15 bg-white/[0.06] px-7 text-base text-white transition-[background-color,scale] hover:bg-white/[0.12] hover:text-white active:scale-[0.96]" size="lg" variant="outline">
                <Link to="/contact">{copy.talkExpert}</Link>
              </Button>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
};

export default Index;
