import type { Language } from '@/i18n/LanguageContext.logic';
import type { ArticleContent, ContentSection } from './contentTypes';
import { videoArticles } from './videoArticles';

type Translation = {
  title: string;
  excerpt: string;
  category: string;
  tags: string[];
  body: ContentSection[];
};

type SupportedTranslationLanguage = Exclude<Language, 'ru'>;

const article = (
  title: string,
  excerpt: string,
  category: string,
  tags: string[],
  body: Array<[string, string]>,
): Translation => ({
  title,
  excerpt,
  category,
  tags,
  body: body.map(([sectionTitle, sectionBody]) => ({ title: sectionTitle, body: sectionBody })),
});

const brief = (
  language: SupportedTranslationLanguage,
  title: string,
  excerpt: string,
  category: string,
  tags: string[],
  paragraphs: [string, string, string],
): Translation => {
  const headings: Record<SupportedTranslationLanguage, [string, string, string]> = {
    en: ['Context', 'What matters', 'Practical conclusion'],
    fr: ['Le contexte', 'Ce qui compte', 'Conclusion pratique'],
    es: ['El contexto', 'Lo importante', 'Conclusión práctica'],
    el: ['Το πλαίσιο', 'Τι έχει σημασία', 'Πρακτικό συμπέρασμα'],
    de: ['Der Kontext', 'Worauf es ankommt', 'Praktisches Fazit'],
    th: ['บริบท', 'สิ่งที่สำคัญ', 'ข้อสรุปเชิงปฏิบัติ'],
    ar: ['السياق', 'ما الذي يهم', 'الخلاصة العملية'],
    ha: ['Yanayin', 'Abin da ya fi muhimmanci', 'Kammalawa mai amfani'],
    tr: ['Bağlam', 'Önemli olan', 'Pratik sonuç'],
  };
  return article(title, excerpt, category, tags, headings[language].map((heading, index) => [heading, paragraphs[index]]));
};

const translations: Record<SupportedTranslationLanguage, Record<string, Translation>> = {
  en: {
    'malyy-biznes-v-2049-godu': article(
      'Small business in 2049: who works while the owner sleeps',
      'A fictional day in a St Petersburg shoe workshop where AI agents handle an order and a robot collects it, while the human remains responsible for the craft.',
      'Business', ['small business', 'AI agents', 'automation', 'future of work'],
      [
        ['An order from 2049', 'An order arrives at night. The owner is asleep, but the customer receives an answer, the system clarifies the job, agrees the price and arranges collection. This is a thought experiment about machines managing the routine parts of a transaction.'],
        ['Agents negotiating for us', 'A customer agent could send structured requirements to the business agent: material, deadline, price, guarantee and delivery. A business will need to be understandable not only to people but also to their digital assistants.'],
        ['Trust becomes machine-readable', 'Automatic transactions need evidence of delivery, refunds and resolved disputes rather than attractive promises. A rating becomes a verifiable history of trust, not merely an average score.'],
        ['What remains human', 'Automation does not make the craftsperson redundant. It makes human judgement more visible: understanding an unusual request, accepting responsibility for exceptions and creating something worth keeping.'],
        ['Start before 2049', 'Describe services so they can be compared, separate routine work from expert decisions, record promises and outcomes, automate repeatable steps and retain human approval for money and public actions.'],
      ],
    ),
    'malyy-biznes-v-drevnem-novgorode': article(
      'How small business worked in medieval Novgorod',
      'Debt, broken agreements, courts and fixed costs existed long before CRM. A day in the life of a fourteenth-century Novgorod entrepreneur.',
      'Business', ['business history', 'entrepreneurship', 'Novgorod', 'management'],
      [
        ['An entrepreneur without a banking app', 'Ships carry goods along the Volkhov, merchants negotiate transport and customers delay payment. The vessel owner has no cash-flow spreadsheet, yet still manages people, deadlines, obligations, costs and risk.'],
        ['The day does not begin with a sale', 'The ship, crew and river conditions must be checked before the first coin is earned. Maintenance and wages continue regardless of today\'s number of customers, just like rent, payroll and equipment do now.'],
        ['Trust is the main capital', 'In a small trading city, reputation travelled faster than advertising. A contract included confidence that the cargo would arrive, the deadline would be met and the carrier would not disappear when trouble began.'],
        ['Accounts receivable are ancient', 'A client could receive the service and pay late. The owner faced a familiar choice: preserve an important relationship or stop work until the old debt was settled.'],
        ['Old questions, modern systems', 'Record agreements, distinguish promised revenue from received cash, calculate downtime and repair, and decide who owns each risk. Technology changes, but sound management still begins with these questions.'],
      ],
    ),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': article(
      'How to manage a business profile on Yandex Maps and 2GIS',
      'A practical routine for services, updates and reviews so the profile helps customers choose instead of becoming another endless content channel.',
      'Maps', ['Yandex Maps', '2GIS', 'business profile', 'LocalOS'],
      [
        ['A profile does not need daily attention', 'A short weekly routine is more useful: check service changes, answer new reviews, publish one relevant update and make sure the core information is still correct.'],
        ['Write services in the customer\'s language', 'People search for a result, not an internal package name. A service should explain what is included, the price or pricing method and any important limitations without repetitive SEO wording.'],
        ['Answer reviews as the owner', 'Future customers read the response too. Refer to the actual message, write like a person and offer a clear next step when something went wrong. Generic gratitude is not a meaningful answer.'],
        ['Publish only when something changed', 'A new specialist, seasonal service, available appointments, changed access or an important restriction is useful news. A vague invitation to visit is not.'],
        ['A 30-minute weekly rhythm', 'Review feedback, update changed details, prepare one useful post and open the profile as a visitor. LocalOS can prepare the work, while publication remains under human review and approval.'],
      ],
    ),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': article(
      'The cult of “I can”: why entrepreneurs struggle to rest',
      'No one forces us to work, yet freedom becomes an endless task list. Why even rest turns into a project and how to regain the right to stop.',
      'Business', ['entrepreneurship', 'rest', 'productivity', 'burnout'],
      [
        ['No boss, yet no stopping', 'An owner chooses the goals and schedule, but work expands into the evening and an empty hour produces anxiety. Freedom quietly becomes a demand to use every possibility.'],
        ['From “you must” to “you can”', 'Byung-Chul Han describes a culture where an external order is replaced by internal possibility. If more is always possible, the current result can never feel sufficient.'],
        ['Rest has become work', 'We optimise sleep, count steps and judge holidays by how efficiently they restore productivity. Time off is no longer free when every hour must justify itself through a future result.'],
        ['Stopping need not be useful', 'A walk may lead nowhere and an evening may improve no metric. Rest is not a reward for completing a list, because an entrepreneur\'s list is never truly complete.'],
        ['The right not to be a function', 'Protect time that has no measurable output, notice guilt without obeying it and share responsibility. A person is more than the function they perform for their business.'],
      ],
    ),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': article(
      'Why customers choose competitors on Yandex Maps',
      'A business may provide excellent service and still lose at the profile stage. These are the signals that make another company easier to choose.',
      'Maps', ['Yandex Maps', 'local search', 'reviews', 'business profile'],
      [
        ['The profile is the shop window', 'Before visiting, a customer compares opening hours, services, prices, reviews, photos and routes. The choice may be made before anyone speaks to the business.'],
        ['You look closed or neglected', 'Old photos, unanswered reviews and stale information create doubt. A competitor whose activity is easier to see feels safer, even when the real quality is similar.'],
        ['The customer cannot recognise their problem', 'Claims about a “full range of quality services” say little. Customers need familiar wording, examples of results, limitations and at least a price guide.'],
        ['Photos must make the visit imaginable', 'Show the entrance, interior, team, process and result. A polished logo cannot answer the practical questions that matter before a first visit.'],
        ['A ten-minute check', 'Search by a customer query, inspect the first mobile screen, compare recent reviews and responses, verify that services and prices are clear, and test the route to the entrance.'],
      ],
    ),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': article(
      'Why customers return to “their place”',
      'Technical quality is not enough. Customers read the space, pace, language and attitude to price, then decide whether they can be themselves there.',
      'Customer experience', ['loyalty', 'customer experience', 'service', 'brand'],
      [
        ['A good result, but no return visit', 'The work may be correct and the price fair, yet the customer also asks whether the place understands them without repeated explanations or pressure.'],
        ['Taste is not merely personal', 'Music, light, language, staff clothing and the way an extra service is offered all signal who the place is for and which behaviour is considered normal.'],
        ['Rules are felt at the entrance', 'A clear welcome, a place for belongings, an explanation of delays and genuine choice answer the visitor\'s first question: must I adapt, or has someone already thought about me?'],
        ['Symbolic capital cannot be declared', 'Reputation and confidence in price grow when promises match behaviour over time. A “premium” label cannot replace calm service, consistent quality and responsible conflict handling.'],
        ['Loyalty permits people to be themselves', 'Strong places have character and need not suit everyone. People return where they do not have to explain themselves again or guess the rules at every visit.'],
      ],
    ),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': article(
      'The history of accounting: from clay tablets to AI',
      'When an operation no longer fits in one person\'s memory, accounting appears. Why business needs an external memory and how numbers help preserve reality.',
      'Business', ['accounting', 'business history', 'KPI', 'AI'],
      [
        ['Business first fits in the owner\'s head', 'With a few orders, one person remembers customers, debts and promises. More staff, channels and suppliers eventually create more relationships than memory can reliably hold.'],
        ['Writing came before theory', 'Clay tablets recorded grain, deliveries and remaining stock. They were external memory: obligations survived after the people involved had left the conversation.'],
        ['Measurement turns nature into a plan', 'Watching river levels helped societies prepare for harvests and taxes. A useful metric still connects an observed change to a decision, rather than existing because it can be counted.'],
        ['A KPI needs a decision', 'Revenue, utilisation, repeat visits and response speed are useful only when someone owns the metric and knows what to do when it rises, falls or stays flat.'],
        ['What AI changes', 'AI can connect signals from reviews, finance and services, but it does not remove the need for reliable data, clear definitions and human approval of external actions.'],
        ['Accounting keeps reality visible', 'The goal is not more tables. It is a shared picture that frees the owner from remembering everything and lets the team act before a problem becomes irreversible.'],
      ],
    ),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': article(
      'Why burnout advice stops helping entrepreneurs',
      'Sleep, exercise and delegation matter, but they do not answer why to continue. A look at owner loneliness and loss of meaning beyond another habit list.',
      'Business', ['burnout', 'entrepreneur loneliness', 'meaning', 'small business'],
      [
        ['You already know the advice', 'Rest, exercise, delegation and fewer notifications can restore energy. But when emptiness returns immediately after a break, the problem is not only the schedule.'],
        ['An owner\'s shift never fully ends', 'Money, key employees, difficult customers and risky decisions continue to live in the owner\'s mind even when nothing is happening. One evening off cannot remove that responsibility.'],
        ['Loneliness is not the absence of people', 'A team and family may be nearby, yet the owner is expected to show confidence rather than uncertainty. Holding all the complexity alone creates isolation.'],
        ['Business can lose its author', 'A small company often begins as a creative act, then obligations and noise take over. The owner maintains the system but rarely meets the reason it was created.'],
        ['A system should reduce loneliness', 'Clear records, shared responsibility and regular reviews move part of the business out of one person\'s head. Recovery may mean redesigning the role and the company, not returning to the old speed.'],
      ],
    ),
  },
  fr: {
    'malyy-biznes-v-2049-godu': brief('fr', 'La petite entreprise en 2049 : qui travaille pendant que le propriétaire dort', 'Une journée imaginaire dans un atelier de chaussures où des agents IA traitent la commande, sans remplacer le jugement humain.', 'Entreprise', ['petite entreprise', 'agents IA', 'automatisation'], ['Une commande arrive la nuit : le système précise le besoin, convient du prix et organise la collecte.', 'Les transactions automatiques exigent des services lisibles et une histoire vérifiable des délais, remboursements et litiges.', 'Décrire clairement les services, automatiser les étapes répétitives et conserver une validation humaine pour les décisions importantes.']),
    'malyy-biznes-v-drevnem-novgorode': brief('fr', 'Comment fonctionnait la petite entreprise dans la Novgorod médiévale', 'Dettes, accords rompus et frais fixes existaient bien avant les logiciels de gestion.', 'Entreprise', ['histoire', 'entrepreneuriat', 'gestion'], ['Un transporteur du XIVe siècle devait gérer son bateau, son équipage, les délais, les paiements et les risques.', 'Dans une petite ville marchande, la confiance circulait plus vite que la publicité et un impayé créait déjà un problème de trésorerie.', 'Fixer les responsabilités, distinguer les promesses des paiements reçus et calculer les coûts avant de donner un prix.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('fr', 'Gérer une fiche d’entreprise sur Yandex Maps et 2GIS', 'Une routine simple pour les services, les actualités et les avis.', 'Cartes', ['Yandex Maps', '2GIS', 'fiche entreprise'], ['Une fiche n’exige pas une publication quotidienne : une vérification courte chaque semaine suffit.', 'Les services doivent parler du résultat, les réponses aux avis doivent être précises et une actualité doit signaler un vrai changement.', 'En trente minutes, traiter les avis, actualiser les informations, préparer une actualité utile et contrôler la fiche comme un visiteur.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('fr', 'Le culte du « je peux » : pourquoi l’entrepreneur a du mal à se reposer', 'La liberté peut devenir une liste de tâches sans fin, jusqu’à transformer le repos en projet.', 'Entreprise', ['repos', 'productivité', 'épuisement'], ['Sans patron, le travail envahit pourtant la soirée et une heure libre provoque de la culpabilité.', 'Quand tout semble possible, aucun résultat ne paraît suffisant et même le sommeil ou les vacances deviennent des outils de performance.', 'Protéger du temps sans objectif mesurable et se rappeler qu’une personne vaut plus que sa fonction dans l’entreprise.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('fr', 'Pourquoi les clients choisissent vos concurrents sur Yandex Maps', 'Un bon service peut perdre avant le premier contact si la fiche inspire moins confiance que celle du concurrent.', 'Cartes', ['recherche locale', 'avis', 'photos'], ['Le client compare horaires, services, prix, avis, photos et itinéraire avant de parler à l’entreprise.', 'Des informations anciennes, des avis sans réponse et des photos abstraites rendent la visite difficile à imaginer.', 'Vérifier le premier écran mobile, les derniers avis, la clarté des prix, les photos de l’entrée et l’itinéraire.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('fr', 'Pourquoi un client revient dans « son endroit »', 'La qualité technique ne suffit pas : l’espace, le rythme et le langage disent au client s’il peut rester lui-même.', 'Expérience client', ['fidélité', 'service', 'marque'], ['Un résultat peut être bon sans provoquer de nouveau rendez-vous si le client doit se justifier ou deviner les règles.', 'La lumière, la musique, les mots et la manière de proposer un service indiquent à qui le lieu s’adresse.', 'La fidélité naît dans un lieu cohérent où la personne n’a pas besoin de s’expliquer à chaque visite.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('fr', 'L’histoire de la comptabilité : des tablettes d’argile à l’IA', 'Quand l’activité ne tient plus dans la mémoire d’une personne, l’entreprise a besoin d’une mémoire extérieure.', 'Entreprise', ['comptabilité', 'KPI', 'IA'], ['Les premières inscriptions conservaient les stocks et les obligations après la fin d’une conversation.', 'Une mesure n’est utile que si elle relie un changement observé à une décision dont quelqu’un est responsable.', 'L’IA relie davantage de signaux, mais exige toujours des données fiables, des définitions claires et une validation humaine.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('fr', 'Pourquoi les conseils contre l’épuisement cessent d’aider les entrepreneurs', 'Dormir et déléguer comptent, mais ne répondent pas toujours à la question du sens.', 'Entreprise', ['épuisement', 'solitude', 'sens'], ['La fatigue ne vient pas seulement de l’emploi du temps lorsque le vide revient aussitôt après une pause.', 'Le propriétaire garde dans sa tête l’argent, l’équipe et les décisions risquées, souvent sans pouvoir partager ses doutes.', 'Des responsabilités claires et des revues communes sortent une partie de l’entreprise de sa tête ; se rétablir peut aussi signifier changer de rôle.']),
  },
  es: {
    'malyy-biznes-v-2049-godu': brief('es', 'La pequeña empresa en 2049: quién trabaja mientras duerme el dueño', 'Un día imaginario en un taller donde agentes de IA gestionan el pedido sin sustituir el criterio humano.', 'Negocios', ['pequeña empresa', 'agentes de IA', 'automatización'], ['Un pedido llega de noche: el sistema aclara el trabajo, acuerda el precio y organiza la recogida.', 'Las operaciones automáticas necesitan servicios comprensibles y un historial verificable de plazos, devoluciones y conflictos.', 'Describir servicios, automatizar pasos repetitivos y mantener la aprobación humana para dinero y acciones públicas.']),
    'malyy-biznes-v-drevnem-novgorode': brief('es', 'Cómo funcionaba la pequeña empresa en la Nóvgorod medieval', 'Deudas, acuerdos incumplidos y costes fijos existían mucho antes del CRM.', 'Negocios', ['historia', 'emprendimiento', 'gestión'], ['Un transportista del siglo XIV gestionaba barco, tripulación, plazos, pagos y riesgos.', 'En una ciudad comercial pequeña, la confianza viajaba más rápido que la publicidad y un impago ya causaba problemas de caja.', 'Fijar responsabilidades, separar promesas de cobros reales y calcular costes antes de poner precio.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('es', 'Cómo gestionar una ficha en Yandex Maps y 2GIS', 'Una rutina práctica para servicios, noticias y reseñas.', 'Mapas', ['Yandex Maps', '2GIS', 'ficha de empresa'], ['No hace falta publicar a diario: basta una revisión breve y constante cada semana.', 'Los servicios deben explicar resultados, las respuestas deben ser concretas y cada noticia debe comunicar un cambio real.', 'En treinta minutos: responder reseñas, actualizar datos, preparar una noticia útil y revisar la ficha como cliente.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('es', 'El culto al «puedo»: por qué al emprendedor le cuesta descansar', 'La libertad puede convertirse en una lista infinita de tareas hasta hacer del descanso otro proyecto.', 'Negocios', ['descanso', 'productividad', 'agotamiento'], ['Sin jefe, el trabajo invade la noche y una hora libre genera culpa.', 'Cuando siempre se puede hacer más, ningún resultado parece suficiente y hasta las vacaciones se miden por su rendimiento.', 'Proteger tiempo sin resultado medible y recordar que la persona es más que su función empresarial.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('es', 'Por qué los clientes eligen a la competencia en Yandex Maps', 'Un buen negocio puede perder antes del contacto si su ficha inspira menos confianza.', 'Mapas', ['búsqueda local', 'reseñas', 'fotos'], ['El cliente compara horarios, servicios, precios, reseñas, fotos y ruta antes de hablar con la empresa.', 'Datos antiguos, reseñas sin respuesta y fotos abstractas impiden imaginar la visita.', 'Revisar la primera pantalla móvil, las reseñas recientes, los precios, la entrada y la ruta.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('es', 'Por qué un cliente vuelve a «su lugar»', 'La calidad técnica no basta: el espacio, el ritmo y el lenguaje indican si puede ser él mismo.', 'Experiencia del cliente', ['fidelidad', 'servicio', 'marca'], ['Un buen resultado no garantiza otra visita si el cliente debe justificarse o adivinar las reglas.', 'La luz, la música, las palabras y la manera de ofrecer extras dicen para quién está pensado el lugar.', 'La fidelidad nace donde la experiencia es coherente y la persona no necesita explicarse de nuevo.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('es', 'Historia de la contabilidad: de las tablillas de arcilla a la IA', 'Cuando el negocio deja de caber en una memoria, necesita una memoria externa.', 'Negocios', ['contabilidad', 'KPI', 'IA'], ['Las primeras anotaciones conservaron existencias y obligaciones después de terminar la conversación.', 'Una métrica sirve cuando conecta un cambio observado con una decisión y un responsable.', 'La IA conecta más señales, pero aún necesita datos fiables, definiciones claras y aprobación humana.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('es', 'Por qué los consejos contra el agotamiento dejan de ayudar al emprendedor', 'Dormir y delegar importan, pero no siempre responden para qué continuar.', 'Negocios', ['agotamiento', 'soledad', 'sentido'], ['Si el vacío vuelve justo después de descansar, el problema no está solo en el horario.', 'El dueño mantiene en su cabeza el dinero, el equipo y las decisiones difíciles, a menudo sin compartir las dudas.', 'Responsabilidades claras y revisiones compartidas reducen esa soledad; recuperarse también puede exigir cambiar el rol.']),
  },
  el: {
    'malyy-biznes-v-2049-godu': brief('el', 'Μικρή επιχείρηση το 2049: ποιος εργάζεται όταν ο ιδιοκτήτης κοιμάται;', 'Μια φανταστική ημέρα όπου πράκτορες ΤΝ διαχειρίζονται την παραγγελία ενώ ο άνθρωπος κρατά την κρίση.', 'Επιχείρηση', ['μικρή επιχείρηση', 'ΤΝ', 'αυτοματισμός'], ['Μια νυχτερινή παραγγελία διευκρινίζεται, κοστολογείται και προγραμματίζεται αυτόματα.', 'Η αυτοματοποίηση απαιτεί καθαρές υπηρεσίες και επαληθεύσιμο ιστορικό αξιοπιστίας.', 'Αυτοματοποιήστε τη ρουτίνα, αλλά διατηρήστε ανθρώπινη έγκριση για χρήματα και δημόσιες ενέργειες.']),
    'malyy-biznes-v-drevnem-novgorode': brief('el', 'Πώς λειτουργούσε η μικρή επιχείρηση στο μεσαιωνικό Νόβγκοροντ', 'Χρέη, αθετημένες συμφωνίες και σταθερά έξοδα υπήρχαν πολύ πριν από το CRM.', 'Επιχείρηση', ['ιστορία', 'επιχειρηματικότητα', 'διοίκηση'], ['Ο μεταφορέας διαχειριζόταν πλοίο, πλήρωμα, προθεσμίες, πληρωμές και κινδύνους.', 'Σε μια μικρή εμπορική πόλη, η φήμη ήταν ισχυρότερη από τη διαφήμιση και η καθυστέρηση πληρωμής έφερνε πρόβλημα ρευστότητας.', 'Καταγράψτε ευθύνες, ξεχωρίστε τις υποσχέσεις από τα έσοδα και υπολογίστε το κόστος πριν την τιμή.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('el', 'Πώς να διαχειρίζεστε ένα επαγγελματικό προφίλ στο Yandex Maps και το 2GIS', 'Μια πρακτική ρουτίνα για υπηρεσίες, νέα και κριτικές.', 'Χάρτες', ['Yandex Maps', '2GIS', 'προφίλ'], ['Το προφίλ δεν χρειάζεται καθημερινή δημοσίευση, αλλά μια σύντομη εβδομαδιαία επιθεώρηση.', 'Οι υπηρεσίες εξηγούν το αποτέλεσμα, οι απαντήσεις είναι συγκεκριμένες και τα νέα αφορούν πραγματικές αλλαγές.', 'Αφιερώστε τριάντα λεπτά σε κριτικές, ενημερώσεις, ένα χρήσιμο νέο και έλεγχο ως πελάτης.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('el', 'Η λατρεία του «μπορώ»: γιατί οι επιχειρηματίες δυσκολεύονται να ξεκουραστούν', 'Η ελευθερία μπορεί να γίνει ατελείωτη λίστα εργασιών.', 'Επιχείρηση', ['ξεκούραση', 'παραγωγικότητα', 'εξουθένωση'], ['Χωρίς αφεντικό, η εργασία παραμένει μέχρι το βράδυ και ο ελεύθερος χρόνος φέρνει ενοχή.', 'Όταν πάντα μπορείς περισσότερα, κανένα αποτέλεσμα δεν αρκεί και ακόμη οι διακοπές μετριούνται με απόδοση.', 'Προστατέψτε χρόνο χωρίς μετρήσιμο στόχο και μην ταυτίζετε τον άνθρωπο με τον ρόλο του.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('el', 'Γιατί οι πελάτες επιλέγουν ανταγωνιστές στο Yandex Maps', 'Μια καλή επιχείρηση μπορεί να χάσει πριν από την πρώτη επαφή αν το προφίλ δεν εμπνέει εμπιστοσύνη.', 'Χάρτες', ['τοπική αναζήτηση', 'κριτικές', 'φωτογραφίες'], ['Ο πελάτης συγκρίνει ωράριο, υπηρεσίες, τιμές, κριτικές, φωτογραφίες και διαδρομή.', 'Παλιές πληροφορίες, αναπάντητες κριτικές και απρόσωπες εικόνες αυξάνουν την αβεβαιότητα.', 'Ελέγξτε την πρώτη οθόνη, τις πρόσφατες κριτικές, τις τιμές, την είσοδο και τη διαδρομή.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('el', 'Γιατί ο πελάτης επιστρέφει στο «δικό του μέρος»', 'Η τεχνική ποιότητα δεν αρκεί: ο χώρος, ο ρυθμός και η γλώσσα δείχνουν αν μπορεί να είναι ο εαυτός του.', 'Εμπειρία πελάτη', ['πιστότητα', 'εξυπηρέτηση', 'μάρκα'], ['Ένα καλό αποτέλεσμα δεν φέρνει πάντα επανάληψη αν ο πελάτης πρέπει να μαντέψει τους κανόνες.', 'Το φως, η μουσική, οι λέξεις και ο τρόπος πρότασης μιλούν για τον χαρακτήρα του μέρου.', 'Η πιστότητα γεννιέται όταν η εμπειρία είναι συνεπής και δεν χρειάζεται να εξηγείς ξανά τον εαυτό σου.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('el', 'Η ιστορία της λογιστικής: από πήλινες πινακίδες στην ΤΝ', 'Όταν η επιχείρηση δεν χωρά στη μνήμη ενός ανθρώπου, χρειάζεται εξωτερική μνήμη.', 'Επιχείρηση', ['λογιστική', 'KPI', 'ΤΝ'], ['Οι πρώτες καταγραφές διατηρούσαν αποθέματα και υποχρεώσεις πέρα από μια συνομιλία.', 'Ένας δείκτης είναι χρήσιμος όταν συνδέει μια αλλαγή με μια απόφαση και έναν υπεύθυνο.', 'Η ΤΝ συνδέει περισσότερα σήματα, αλλά χρειάζεται αξιόπιστα δεδομένα, καθαρούς ορισμούς και ανθρώπινη έγκριση.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('el', 'Γιατί οι συμβουλές για την εξουθένωση παύουν να βοηθούν τον επιχειρηματία', 'Ο ύπνος και η ανάθεση βοηθούν, αλλά δεν απαντούν πάντα στο ερώτημα του νοήματος.', 'Επιχείρηση', ['εξουθένωση', 'μοναξιά', 'νόημα'], ['Όταν το κενό επιστρέφει αμέσως μετά την ανάπαυση, το πρόβλημα δεν είναι μόνο το πρόγραμμα.', 'Τα χρήματα, η ομάδα και οι δύσκολες αποφάσεις παραμένουν στο μυαλό του ιδιοκτήτη, ενώ οι αμφιβολίες δύσκολα μοιράζονται.', 'Καθαρές ευθύνες και κοινές ανασκοπήσεις μειώνουν τη μοναξιά· η ανάκαμψη ίσως απαιτεί νέο ρόλο.']),
  },
  de: {
    'malyy-biznes-v-2049-godu': brief('de', 'Kleinunternehmen im Jahr 2049: Wer arbeitet, während der Inhaber schläft?', 'Ein fiktiver Tag in einer Werkstatt, in der KI-Agenten den Auftrag abwickeln, ohne menschliches Urteil zu ersetzen.', 'Unternehmen', ['Kleinunternehmen', 'KI-Agenten', 'Automatisierung'], ['Nachts trifft ein Auftrag ein: Das System klärt die Aufgabe, vereinbart den Preis und organisiert die Abholung.', 'Automatische Geschäfte brauchen verständliche Leistungen und eine prüfbare Historie von Terminen, Erstattungen und Konflikten.', 'Leistungen klar beschreiben, Routine automatisieren und menschliche Freigaben für Geld und öffentliche Handlungen behalten.']),
    'malyy-biznes-v-drevnem-novgorode': brief('de', 'Wie Kleinunternehmen im mittelalterlichen Nowgorod arbeiteten', 'Schulden, gebrochene Absprachen und Fixkosten gab es lange vor CRM.', 'Unternehmen', ['Geschichte', 'Unternehmertum', 'Management'], ['Ein Frachtunternehmer des 14. Jahrhunderts steuerte Schiff, Mannschaft, Fristen, Zahlungen und Risiken.', 'In der Handelsstadt verbreitete sich Vertrauen schneller als Werbung; verspätete Zahlungen erzeugten schon damals Liquiditätsprobleme.', 'Verantwortung festlegen, versprochenen Umsatz von echtem Geldeingang trennen und Kosten vor dem Preis berechnen.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('de', 'Ein Unternehmensprofil auf Yandex Maps und 2GIS pflegen', 'Ein praktischer Rhythmus für Leistungen, Neuigkeiten und Bewertungen.', 'Karten', ['Yandex Maps', '2GIS', 'Unternehmensprofil'], ['Ein Profil braucht keine täglichen Beiträge, sondern eine kurze wöchentliche Kontrolle.', 'Leistungen erklären Ergebnisse, Antworten greifen konkrete Bewertungen auf und Neuigkeiten melden echte Veränderungen.', 'In dreißig Minuten Bewertungen bearbeiten, Daten aktualisieren, einen nützlichen Beitrag erstellen und das Profil wie ein Kunde prüfen.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('de', 'Der Kult des „Ich kann“: Warum Unternehmer schwer abschalten', 'Freiheit kann zur endlosen Aufgabenliste werden und selbst Erholung zum Projekt machen.', 'Unternehmen', ['Erholung', 'Produktivität', 'Burnout'], ['Ohne Chef reicht die Arbeit trotzdem bis in den Abend und freie Zeit erzeugt Schuldgefühle.', 'Wenn immer mehr möglich ist, wirkt kein Ergebnis ausreichend und sogar Urlaub wird nach Leistung bewertet.', 'Zeit ohne messbares Ziel schützen und den Menschen nicht auf seine Funktion im Unternehmen reduzieren.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('de', 'Warum Kunden auf Yandex Maps Wettbewerber wählen', 'Ein gutes Unternehmen kann vor dem ersten Kontakt verlieren, wenn sein Profil weniger Vertrauen schafft.', 'Karten', ['lokale Suche', 'Bewertungen', 'Fotos'], ['Kunden vergleichen Öffnungszeiten, Leistungen, Preise, Bewertungen, Fotos und Anfahrt.', 'Veraltete Angaben, unbeantwortete Bewertungen und unpersönliche Bilder machen den Besuch schwer vorstellbar.', 'Den ersten mobilen Bildschirm, aktuelle Bewertungen, Preise, Eingangsfotos und Route in zehn Minuten prüfen.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('de', 'Warum Kunden an „ihr Stammlokal“ zurückkehren', 'Technische Qualität reicht nicht: Raum, Tempo und Sprache zeigen, ob jemand dort er selbst sein kann.', 'Kundenerlebnis', ['Loyalität', 'Service', 'Marke'], ['Ein gutes Ergebnis führt nicht automatisch zum nächsten Besuch, wenn Kunden Regeln erraten oder sich rechtfertigen müssen.', 'Licht, Musik, Sprache und Zusatzangebote signalisieren, für wen ein Ort gedacht ist.', 'Loyalität entsteht durch ein stimmiges Erlebnis, bei dem man sich nicht jedes Mal neu erklären muss.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('de', 'Geschichte der Buchhaltung: Von Tontafeln zur KI', 'Wenn ein Betrieb nicht mehr in den Kopf eines Menschen passt, braucht er ein externes Gedächtnis.', 'Unternehmen', ['Buchhaltung', 'KPI', 'KI'], ['Frühe Aufzeichnungen bewahrten Bestände und Verpflichtungen über ein Gespräch hinaus.', 'Eine Kennzahl ist nützlich, wenn sie eine beobachtete Veränderung mit einer Entscheidung und Verantwortung verbindet.', 'KI verbindet mehr Signale, braucht aber weiterhin verlässliche Daten, klare Definitionen und menschliche Freigabe.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('de', 'Warum Burnout-Ratschläge Unternehmern irgendwann nicht mehr helfen', 'Schlaf und Delegation sind wichtig, beantworten aber nicht immer die Frage nach dem Sinn.', 'Unternehmen', ['Burnout', 'Einsamkeit', 'Sinn'], ['Kehrt die Leere direkt nach einer Pause zurück, liegt das Problem nicht nur im Terminkalender.', 'Geld, Team und schwierige Entscheidungen bleiben im Kopf des Inhabers, obwohl Zweifel kaum geteilt werden.', 'Klare Verantwortung und gemeinsame Rückblicke verringern die Einsamkeit; Erholung kann auch eine neue Rolle verlangen.']),
  },
  th: {
    'malyy-biznes-v-2049-godu': brief('th', 'ธุรกิจขนาดเล็กในปี 2049: ใครทำงานขณะเจ้าของหลับ', 'ภาพสมมติของร้านที่ตัวแทน AI จัดการคำสั่งซื้อ แต่มนุษย์ยังเป็นผู้ตัดสินใจ', 'ธุรกิจ', ['ธุรกิจขนาดเล็ก','AI','ระบบอัตโนมัติ'], ['ระบบช่วยชี้แจงงาน ตกลงราคาและจัดการรับสินค้าได้แม้เจ้าของหลับ', 'การทำธุรกรรมอัตโนมัติต้องมีข้อมูลบริการและประวัติความไว้วางใจที่ตรวจสอบได้', 'ทำงานซ้ำให้เป็นอัตโนมัติ แต่คงการอนุมัติของมนุษย์ไว้สำหรับเงินและการกระทำสาธารณะ']),
    'malyy-biznes-v-drevnem-novgorode': brief('th', 'ธุรกิจขนาดเล็กในนอฟโกรอดยุคกลาง', 'หนี้สิน ข้อตกลงที่ล้มเหลวและต้นทุนคงที่มีมาก่อน CRM', 'ธุรกิจ', ['ประวัติศาสตร์','การจัดการ'], ['ผู้ขนส่งต้องจัดการเรือ ลูกเรือ กำหนดเวลา การชำระเงินและความเสี่ยง', 'ชื่อเสียงเดินทางเร็วกว่าโฆษณา และการจ่ายช้าก็สร้างปัญหาเงินสด', 'กำหนดความรับผิดชอบ แยกรายได้ที่สัญญาจากเงินที่ได้รับ และคำนวณต้นทุนก่อนตั้งราคา']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('th', 'วิธีจัดการโปรไฟล์ธุรกิจบน Yandex Maps และ 2GIS', 'ขั้นตอนรายสัปดาห์สำหรับบริการ ข่าวและรีวิว', 'แผนที่', ['Yandex Maps','2GIS','โปรไฟล์ธุรกิจ'], ['ไม่ต้องโพสต์ทุกวัน แต่ควรตรวจสอบอย่างสม่ำเสมอทุกสัปดาห์', 'บริการต้องบอกผลลัพธ์ คำตอบต้องเฉพาะเจาะจง และข่าวต้องบอกการเปลี่ยนแปลงจริง', 'ใช้เวลา 30 นาทีตอบรีวิว อัปเดตข้อมูล เขียนข่าวที่มีประโยชน์ และดูโปรไฟล์เหมือนลูกค้า']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('th', 'วัฒนธรรม “ฉันทำได้”: ทำไมผู้ประกอบการจึงพักยาก', 'เสรีภาพอาจกลายเป็นรายการงานไม่สิ้นสุด', 'ธุรกิจ', ['การพัก','ผลิตภาพ','หมดไฟ'], ['แม้ไม่มีเจ้านาย งานก็ยังล้นถึงตอนค่ำและเวลาว่างก็ทำให้รู้สึกผิด', 'เมื่อทำได้มากขึ้นเสมอ ผลลัพธ์ใดก็ดูไม่พอ แม้แต่วันหยุดก็ถูกวัดด้วยประสิทธิภาพ', 'ปกป้องเวลาที่ไม่มีเป้าหมายวัดผลได้ และอย่าลดคนให้เหลือเพียงหน้าที่ในธุรกิจ']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('th', 'ทำไมลูกค้าเลือกคู่แข่งบน Yandex Maps', 'ธุรกิจที่ดีอาจแพ้ก่อนการติดต่อครั้งแรกหากโปรไฟล์ไม่น่าเชื่อถือ', 'แผนที่', ['ค้นหาท้องถิ่น','รีวิว','รูปภาพ'], ['ลูกค้าเปรียบเทียบเวลา บริการ ราคา รีวิว รูปภาพและเส้นทาง', 'ข้อมูลเก่า รีวิวที่ไม่ตอบและรูปที่ไม่ชัดเจนทำให้จินตนาการการเยี่ยมชมได้ยาก', 'ตรวจหน้าจอแรก รีวิวล่าสุด ราคา รูปทางเข้าและเส้นทาง']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('th', 'ทำไมลูกค้าจึงกลับมายัง “สถานที่ของตน”', 'คุณภาพทางเทคนิคไม่พอ พื้นที่ จังหวะและภาษาบอกว่าลูกค้าเป็นตัวเองได้หรือไม่', 'ประสบการณ์ลูกค้า', ['ความภักดี','บริการ','แบรนด์'], ['ผลงานที่ดีอาจไม่นำไปสู่การกลับมาหากลูกค้าต้องเดากฎหรือปกป้องตนเอง', 'แสง ดนตรี คำพูดและวิธีเสนอบริการเสริมสื่อถึงลักษณะของสถานที่', 'ความภักดีเกิดจากประสบการณ์ที่สอดคล้องซึ่งไม่ต้องอธิบายตนเองซ้ำ']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('th', 'ประวัติการบัญชี: จากแผ่นดินเหนียวถึง AI', 'เมื่อธุรกิจใหญ่เกินความทรงจำของคนเดียว จึงต้องมีความทรงจำภายนอก', 'ธุรกิจ', ['บัญชี','KPI','AI'], ['บันทึกแรกช่วยเก็บสต็อกและภาระผูกพันไว้หลังการสนทนาจบลง', 'ตัวชี้วัดมีประโยชน์เมื่อเชื่อมการเปลี่ยนแปลงกับการตัดสินใจและผู้รับผิดชอบ', 'AI รวมสัญญาณได้มากขึ้น แต่ยังต้องมีข้อมูลที่เชื่อถือได้ คำนิยามชัดเจนและการอนุมัติของมนุษย์']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('th', 'ทำไมคำแนะนำเรื่องหมดไฟจึงหยุดช่วยผู้ประกอบการ', 'การนอนและมอบหมายงานสำคัญ แต่ไม่ได้ตอบเรื่องความหมายเสมอไป', 'ธุรกิจ', ['หมดไฟ','ความโดดเดี่ยว','ความหมาย'], ['หากความว่างเปล่ากลับมาทันทีหลังพัก ปัญหาไม่ได้อยู่ที่ตารางเท่านั้น', 'เงิน ทีมและการตัดสินใจยากๆ คงอยู่ในหัวเจ้าของ ขณะที่ความสงสัยแบ่งปันได้ยาก', 'ความรับผิดชอบที่ชัดเจนและการทบทวนร่วมกันลดความโดดเดี่ยว การฟื้นตัวอาจหมายถึงการเปลี่ยนบทบาท']),
  },
  ar: {
    'malyy-biznes-v-2049-godu': brief('ar', 'المشروع الصغير في 2049: من يعمل بينما ينام المالك؟', 'يوم خيالي تدير فيه وكلاء الذكاء الاصطناعي الطلب مع بقاء الحكم للإنسان.', 'الأعمال', ['مشروع صغير','ذكاء اصطناعي','أتمتة'], ['يوضح النظام المهمة ويتفق على السعر وينظم الاستلام أثناء نوم المالك.', 'تحتاج المعاملات الآلية إلى خدمات واضحة وسجل ثقة قابل للتحقق.', 'أتمت الخطوات المتكررة وأبق الموافقة البشرية للأموال والإجراءات العامة.']),
    'malyy-biznes-v-drevnem-novgorode': brief('ar', 'كيف عملت المشروعات الصغيرة في نوفغورود الوسيطة', 'كانت الديون والاتفاقات المخفقة والتكاليف الثابتة موجودة قبل CRM.', 'الأعمال', ['تاريخ','ريادة','إدارة'], ['كان الناقل يدير السفينة والطاقم والمواعيد والمدفوعات والمخاطر.', 'في مدينة تجارية صغيرة انتشرت السمعة أسرع من الإعلان وسبب الدفع المتأخر أزمة نقدية.', 'حدد المسؤوليات وافصل الوعود عن النقود المستلمة واحسب التكلفة قبل التسعير.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('ar', 'كيفية إدارة ملف النشاط على Yandex Maps و‎2GIS', 'روتين عملي للخدمات والأخبار والمراجعات.', 'الخرائط', ['Yandex Maps','2GIS','ملف النشاط'], ['لا يحتاج الملف إلى نشر يومي بل إلى مراجعة أسبوعية منتظمة.', 'اشرح نتيجة الخدمة، واردد بشكل محدد، وانشر فقط عندما يتغير شيء يهم العميل.', 'خصص ثلاثين دقيقة للرد والتحديث وإعداد خبر مفيد وفحص الملف كعميل.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('ar', 'ثقافة «أستطيع»: لماذا يصعب على رائد الأعمال الراحة؟', 'قد تتحول الحرية إلى قائمة مهام بلا نهاية.', 'الأعمال', ['راحة','إنتاجية','إرهاق'], ['يمتد العمل إلى المساء ويولد الوقت الفارغ شعورا بالذنب حتى من دون مدير.', 'عندما يكون المزيد ممكنا دائما، لا تبدو أي نتيجة كافية وتقاس العطلة بالكفاءة.', 'احم وقتا بلا نتيجة قابلة للقياس ولا تختزل الإنسان في وظيفته.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('ar', 'لماذا يختار العملاء المنافسين على Yandex Maps؟', 'قد يخسر النشاط الجيد قبل أول اتصال إذا كان ملفه أقل ثقة.', 'الخرائط', ['بحث محلي','مراجعات','صور'], ['يقارن العميل الساعات والخدمات والأسعار والمراجعات والصور والطريق.', 'البيانات القديمة والمراجعات بلا رد والصور العامة تجعل الزيارة غير واضحة.', 'راجع الشاشة الأولى والمراجعات والأسعار وصور المدخل والطريق.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('ar', 'لماذا يعود العميل إلى «مكانه»؟', 'الجودة التقنية لا تكفي؛ المكان والإيقاع واللغة تحدد ما إذا كان يستطيع أن يكون نفسه.', 'تجربة العميل', ['ولاء','خدمة','علامة'], ['قد لا تؤدي النتيجة الجيدة إلى زيارة جديدة إذا اضطر العميل لتخمين القواعد.', 'الضوء والموسيقى والكلمات وطريقة عرض الإضافات توضح لمن صمم المكان.', 'ينشأ الولاء من تجربة متسقة لا يحتاج فيها الشخص إلى شرح نفسه مرة أخرى.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('ar', 'تاريخ المحاسبة: من الألواح الطينية إلى الذكاء الاصطناعي', 'عندما لا يعود العمل يتسع في ذاكرة شخص واحد يحتاج إلى ذاكرة خارجية.', 'الأعمال', ['محاسبة','KPI','ذكاء اصطناعي'], ['حفظت السجلات المبكرة المخزون والالتزامات بعد انتهاء الحديث.', 'يفيد المؤشر عندما يربط التغير الملحوظ بقرار ومسؤول.', 'يربط الذكاء سيلا أكبر من الإشارات، لكنه يحتاج بيانات موثوقة وتعريفات واضحة وموافقة بشرية.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('ar', 'لماذا تتوقف نصائح الإرهاق عن مساعدة رائد الأعمال؟', 'النوم والتفويض مهمان، لكنهما لا يجيبان دائما عن سؤال المعنى.', 'الأعمال', ['إرهاق','وحدة','معنى'], ['إذا عاد الفراغ مباشرة بعد الراحة، فالمشكلة ليست في الجدول فقط.', 'يبقى المال والفريق والقرارات الصعبة في رأس المالك ويصعب عليه مشاركة شكوكه.', 'تقلل المسؤوليات الواضحة والمراجعات المشتركة الوحدة؛ وقد يتطلب التعافي تغيير الدور.']),
  },
  ha: {
    'malyy-biznes-v-2049-godu': brief('ha', 'Ƙaramar kasuwanci a 2049: wa ke aiki yayin da mai shi yake barci?', 'Ranar kirkira inda wakilan AI ke kula da oda, amma mutum ya ci gaba da yanke hukunci.', 'Kasuwanci', ['ƙaramar kasuwanci','AI','aikin atomatik'], ['Tsari yana fayyace aiki, ya amince da farashi kuma ya shirya karɓa kaya da dare.', 'Mu’amala ta atomatik tana buƙatar bayyanannun ayyuka da tarihin amana da za a iya tabbatarwa.', 'A sarrafa ayyukan maimaituwa, amma mutum ya amince da kuɗi da ayyukan jama’a.']),
    'malyy-biznes-v-drevnem-novgorode': brief('ha', 'Yadda ƙaramar kasuwanci ta yi aiki a Novgorod na da', 'Bashi, karya yarjejeniya da tsayayyen kuɗi sun wanzu tun kafin CRM.', 'Kasuwanci', ['tarihi','harkar kasuwanci','gudanarwa'], ['Mai jigilar kaya ya kula da jirgi, ma’aikata, lokaci, biyan kuɗi da haɗari.', 'A ƙaramar birnin ciniki suna ya fi talla saurin yaduwa, jinkirin biya kuma ya kawo matsalar kuɗi.', 'A rubuta alhaki, a raba alƙawarin kuɗin shiga da kuɗin da aka karɓa, a lissafta kuɗi kafin farashi.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('ha', 'Yadda ake kula da bayanin kasuwanci a Yandex Maps da 2GIS', 'Tsarin mako-mako don ayyuka, labarai da ra’ayoyi.', 'Taswira', ['Yandex Maps','2GIS','bayanin kasuwanci'], ['Ba a buƙatar wallafa kullum; ana buƙatar taƙaitaccen dubawa kowane mako.', 'Ayyuka su bayyana sakamako, amsoshi su kasance na musamman, labari kuma ya faɗi ainihin sauyi.', 'A minti talatin a amsa ra’ayoyi, a sabunta bayanai, a shirya labari mai amfani sannan a duba shafin kamar abokin ciniki.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('ha', 'Al’adar “ina iya”: me ya sa ’yan kasuwa ke kasa hutawa?', '’Yanci na iya zama jerin ayyuka marasa ƙarewa har hutu ya koma wani aiki.', 'Kasuwanci', ['hutu','inganci','gajiya'], ['Ko babu shugaba, aiki yana shiga dare kuma lokacin banza yana haifar da laifi.', 'Idan ana iya yin ƙari koyaushe, babu sakamakon da ya isa, har hutu ana auna shi da inganci.', 'A kare lokacin da ba shi da sakamako mai auna kuma kada a rage mutum zuwa aikinsa kawai.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('ha', 'Me ya sa kwastomomi ke zaɓar masu gasa a Yandex Maps?', 'Kasuwanci mai kyau na iya yin rashin nasara kafin hulɗa idan bayaninsa bai ba da amana ba.', 'Taswira', ['binciken gida','ra’ayoyi','hotuna'], ['Kwastoma yana kwatanta lokaci, ayyuka, farashi, ra’ayoyi, hotuna da hanya kafin ya yi magana.', 'Tsoffin bayanai, ra’ayoyin da ba a amsa ba da hotuna marasa bayani suna sa ziyara ta zama ba a sani ba.', 'A duba allon farko, sabbin ra’ayoyi, farashi, hoton ƙofa da hanya.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('ha', 'Me ya sa kwastoma ke komawa “wurinsa”?', 'Ingancin fasaha bai isa ba; wuri, sauri da harshe suna nuna ko mutum zai iya zama kansa.', 'Kwarewar kwastoma', ['aminci','hidima','alama'], ['Kyakkyawan sakamako ba zai kawo dawowa ba idan kwastoma yana hasashen dokoki ko kare zaɓinsa.', 'Haske, kiɗa, kalmomi da yadda ake ba da ƙarin hidima suna nuna wanda aka tsara wurin dominsa.', 'Aminci yana tasowa daga kwarewa mai daidaito inda mutum ba ya sake bayyana kansa kowane lokaci.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('ha', 'Tarihin lissafi: daga allunan laka zuwa AI', 'Lokacin da kasuwanci ya fi ƙarfin tunanin mutum ɗaya, yana buƙatar wata ƙwaƙwalwa ta waje.', 'Kasuwanci', ['lissafi','KPI','AI'], ['Rubuce-rubucen farko sun riƙe kaya da alhaki bayan tattaunawa ta ƙare.', 'Ma’auni yana da amfani idan ya haɗa sauyin da aka gani da yanke hukunci da mai alhaki.', 'AI yana haɗa alamomi da yawa, amma har yanzu yana buƙatar sahihan bayanai, ma’ana bayyananniya da amincewar mutum.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('ha', 'Me ya sa shawarar gajiya ta daina taimakon ’yan kasuwa?', 'Barci da raba aiki suna da muhimmanci, amma ba koyaushe suke amsa tambayar ma’ana ba.', 'Kasuwanci', ['gajiya','kaɗaici','ma’ana'], ['Idan fanko ya dawo nan da nan bayan hutu, matsalar ba jadawali kaɗai ba ce.', 'Kuɗi, ma’aikata da yanke hukunci masu wuya suna ci gaba da zama a zuciyar mai shi, yayin da raba shakku ke da wuya.', 'Bayyanannen alhaki da bitar tare suna rage kaɗaici; murmurewa na iya nufin sauya rawar mai shi.']),
  },
  tr: {
    'malyy-biznes-v-2049-godu': brief('tr', '2049’da küçük işletme: sahibi uyurken kim çalışacak?', 'Yapay zekâ ajanlarının siparişi yönettiği, insanın ise kararın sahibi kaldığı hayalî bir atölye günü.', 'İşletme', ['küçük işletme', 'yapay zekâ', 'otomasyon'], ['Gece gelen siparişte sistem ihtiyacı netleştirir, fiyatı onaylar ve teslim almayı düzenler.', 'Otomatik işlemler anlaşılır hizmetler ve süre, iade, uyuşmazlık konusunda doğrulanabilir bir geçmiş ister.', 'Hizmetleri açık anlatın, tekrarı otomatikleştirin; para ve kamusal işlemlerde insan onayını koruyun.']),
    'malyy-biznes-v-drevnem-novgorode': brief('tr', 'Orta Çağ Novgorod’unda küçük işletmeler nasıl çalışıyordu?', 'Borçlar, bozulan anlaşmalar ve sabit giderler CRM’den çok önce vardı.', 'İşletme', ['tarih', 'girişimcilik', 'yönetim'], ['On dördüncü yüzyıl taşımacısı tekne, ekip, süre, ödeme ve riski birlikte yönetiyordu.', 'Küçük ticaret kentinde güven reklamdan hızlı yayılıyor, geciken ödeme nakit açığı yaratıyordu.', 'Sorumluluğu yazın, vaat edilen geliri alınan paradan ayırın ve fiyat vermeden önce maliyeti hesaplayın.']),
    'kak-vesti-kartochku-biznesa-v-yandeks-kartah-i-2gis': brief('tr', 'Yandex Maps ve 2GIS’te işletme profili nasıl yönetilir?', 'Hizmetler, haberler ve yorumlar için uygulanabilir bir haftalık düzen.', 'Haritalar', ['Yandex Maps', '2GIS', 'işletme profili'], ['Profil her gün içerik değil, haftada bir kısa ve düzenli kontrol ister.', 'Hizmetler sonucu anlatmalı, yorum yanıtı somut olmalı, haber ise gerçek bir değişikliği bildirmelidir.', 'Otuz dakikada yorumları yanıtlayın, bilgileri güncelleyin, yararlı bir haber hazırlayın ve profili müşteri gibi kontrol edin.']),
    'kult-mogu-pochemu-predprinimateli-ne-umeyut-otdyhat': brief('tr', '“Yapabilirim” kültü: Girişimci neden dinlenemez?', 'Özgürlük sonsuz bir görev listesine, dinlenme de başka bir projeye dönüşebilir.', 'İşletme', ['dinlenme', 'verimlilik', 'tükenmişlik'], ['Patron olmasa da iş akşama taşar ve boş bir saat suçluluk yaratır.', 'Her zaman daha fazlası mümkünse hiçbir sonuç yeterli gelmez; tatil bile verimle ölçülür.', 'Ölçülebilir sonucu olmayan zamanı koruyun ve insanı işletmedeki işlevinden ibaret görmeyin.']),
    'pochemu-klienty-vybirayut-konkurentov-na-yandeks-kartah': brief('tr', 'Müşteriler Yandex Maps’te neden rakipleri seçiyor?', 'İyi bir işletme, profili rakibinden daha az güven verdiği için ilk temastan önce kaybedebilir.', 'Haritalar', ['yerel arama', 'yorumlar', 'fotoğraflar'], ['Müşteri konuşmadan önce saatleri, hizmetleri, fiyatı, yorumları, fotoğrafları ve rotayı karşılaştırır.', 'Eski bilgiler, yanıtsız yorumlar ve soyut görseller ziyareti hayal etmeyi zorlaştırır.', 'Mobil ilk ekranı, son yorumları, fiyatları, giriş fotoğraflarını ve rotayı kontrol edin.']),
    'pochemu-klient-vozvrashchaetsya-v-svoe-mesto': brief('tr', 'Müşteri neden “kendi yerine” geri döner?', 'Teknik kalite yetmez; mekân, tempo ve dil kişinin orada kendisi olup olamayacağını gösterir.', 'Müşteri deneyimi', ['sadakat', 'hizmet', 'marka'], ['Müşteri kuralları tahmin etmek veya kendini savunmak zorundaysa iyi sonuç yeni ziyaret getirmeyebilir.', 'Işık, müzik, kelimeler ve ek hizmet sunma biçimi mekânın kimin için olduğunu anlatır.', 'Sadakat, insanın her ziyarette kendini yeniden açıklamadığı tutarlı bir deneyimden doğar.']),
    'istoriya-ucheta-ot-glinyanyh-tablichek-do-ii': brief('tr', 'Muhasebenin tarihi: Kil tabletlerden yapay zekâya', 'İş tek kişinin hafızasına sığmadığında dış hafızaya ihtiyaç duyar.', 'İşletme', ['muhasebe', 'KPI', 'yapay zekâ'], ['İlk kayıtlar stokları ve yükümlülükleri konuşma bittikten sonra da korudu.', 'Bir gösterge, gözlenen değişimi sorumlusu belli bir karara bağladığında yararlıdır.', 'Yapay zekâ daha çok sinyali birleştirir; yine de güvenilir veri, açık tanım ve insan onayı gerekir.']),
    'pochemu-sovety-ot-vygoraniya-ne-pomogayut-predprinimatelyu': brief('tr', 'Tükenmişlik tavsiyeleri girişimciye neden artık yardım etmez?', 'Uyku ve yetki devri önemlidir, fakat devam etmenin anlamını her zaman açıklamaz.', 'İşletme', ['tükenmişlik', 'yalnızlık', 'anlam'], ['Boşluk dinlenmeden hemen sonra geri dönüyorsa sorun yalnızca program değildir.', 'Para, ekip ve zor kararlar sahibinin zihninde kalır; oysa kuşkuları paylaşmak çoğu zaman zordur.', 'Açık sorumluluk ve ortak değerlendirme yalnızlığı azaltır; iyileşme rolü değiştirmeyi de gerektirebilir.']),
  },
};

const relatedLabel: Record<Language, string> = {
  ru: 'Статья', en: 'Article', fr: 'Article', es: 'Artículo', el: 'Άρθρο', de: 'Artikel',
  th: 'บทความ', ar: 'مقال', ha: 'Maƙala', tr: 'Makale',
};

export const localizedVideoArticles = (language: SupportedTranslationLanguage): ArticleContent[] => {
  const localized = translations[language];
  return videoArticles.map((source) => {
    const translation = localized[source.slug];
    if (!translation) {
      throw new Error(`Missing ${language} translation for video article ${source.slug}`);
    }
    return {
      ...source,
      ...translation,
      seoTitle: translation.title,
      seoDescription: translation.excerpt,
      video: source.video ? { ...source.video, title: translation.title } : undefined,
      related: source.related.map((item) => ({
        ...item,
        title: localized[item.href.replace('/articles/', '')]?.title ?? item.title,
        label: relatedLabel[language],
      })),
    };
  });
};
