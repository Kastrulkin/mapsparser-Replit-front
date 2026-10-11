import type {
  ManagedCardGrowthActionCode,
  ManagedCardGrowthActionCopy,
  ManagedCardGrowthCopy,
} from './managedCardGrowthCopy';

type EuropeanLanguage = 'fr' | 'de' | 'tr';

type EuropeanActionText = {
  title: (provider: string) => string;
  reason: (provider: string, params: { benchmarkMedian?: number }) => string;
  cta: string;
};

const goals: Record<EuropeanLanguage, Record<string, string>> = {
  fr: {
    inquiries: 'Faciliter la prise de contact et vérifier l’évolution des actions confirmées sur la fiche.',
    bookings: 'Faciliter la réservation et vérifier l’évolution des réservations ou des demandes.',
    orders: 'Faciliter la commande et vérifier l’évolution des commandes ou des demandes.',
    directions: 'Rendre la visite plus claire et vérifier l’évolution des itinéraires calculés.',
    website_visits: 'Rendre le lien vers le site plus visible et vérifier l’évolution des clics.',
  },
  de: {
    inquiries: 'Die Kontaktaufnahme vereinfachen und die Veränderung bestätigter Aktionen im Eintrag prüfen.',
    bookings: 'Die Buchung vereinfachen und die Veränderung von Buchungen oder Anfragen prüfen.',
    orders: 'Die Bestellung vereinfachen und die Veränderung von Bestellungen oder Anfragen prüfen.',
    directions: 'Den Besuch verständlicher machen und die Veränderung berechneter Routen prüfen.',
    website_visits: 'Den Übergang zur Website sichtbarer machen und die Veränderung der Klicks prüfen.',
  },
  tr: {
    inquiries: 'İletişime geçmeyi kolaylaştırın ve karttaki doğrulanmış işlemlerin değişimini kontrol edin.',
    bookings: 'Rezervasyonu kolaylaştırın ve rezervasyonlar ya da başvurulardaki değişimi kontrol edin.',
    orders: 'Siparişi kolaylaştırın ve siparişler ya da başvurulardaki değişimi kontrol edin.',
    directions: 'Ziyareti daha anlaşılır hâle getirin ve oluşturulan rotalardaki değişimi kontrol edin.',
    website_visits: 'Web sitesine geçişi daha görünür kılın ve tıklamalardaki değişimi kontrol edin.',
  },
};

const withMedian = (base: string, median: number | undefined, language: EuropeanLanguage) => {
  if (median == null || !Number.isFinite(median)) return base;
  const locale = language === 'fr' ? 'fr-FR' : language === 'de' ? 'de-DE' : 'tr-TR';
  const value = new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(median);
  const suffix = language === 'fr'
    ? ` La médiane des fiches comparables est de ${value}.`
    : language === 'de'
      ? ` Der Median vergleichbarer Einträge liegt bei ${value}.`
      : ` Benzer kartlardaki medyan ${value}.`;
  return `${base}${suffix}`;
};

const action = (title: (provider: string) => string, reason: string, cta: string, language: EuropeanLanguage): EuropeanActionText => ({
  title,
  reason: (_provider, params) => withMedian(reason, params.benchmarkMedian, language),
  cta,
});

const actionTexts: Record<EuropeanLanguage, Record<ManagedCardGrowthActionCode, EuropeanActionText>> = {
  fr: {
    refresh: action((provider) => `Actualisez les données ${provider}`, 'Une nouvelle capture de la fiche est nécessaire pour choisir la première correction.', 'Actualiser les données', 'fr'),
    restore: action((provider) => `Rétablissez l’actualisation ${provider}`, 'La dernière actualisation a échoué. Rétablissez d’abord la source.', 'Vérifier la connexion', 'fr'),
    add_provider: action(() => 'Ajoutez une plateforme à vérifier', 'LocalOS ne sait pas encore quelles fiches appartiennent à cet établissement. Ajoutez Google, Yandex ou 2GIS pour obtenir une première capture.', 'Ajouter une plateforme', 'fr'),
    blocked: action((provider) => `Rétablissez l’actualisation ${provider}`, 'La plateforme ne fournit temporairement pas de données fiables. Rétablissez d’abord la source.', 'Vérifier la connexion', 'fr'),
    access: action((provider) => `Connectez la fiche ${provider}`, 'Sans connexion, LocalOS ne peut pas vérifier la fiche ni suivre le résultat.', 'Ajouter une plateforme', 'fr'),
    verified: action((provider) => `Vérifiez la gestion de la fiche dans ${provider}`, 'La plateforme ne confirme pas que la fiche est gérée par l’établissement.', 'Ouvrir la fiche', 'fr'),
    duplicate: action((provider) => `Vérifiez les doublons dans ${provider}`, 'Un doublon peut répartir les avis et induire les clients en erreur.', 'Vérifier la fiche', 'fr'),
    category: action((provider) => `Précisez la catégorie principale dans ${provider}`, 'La catégorie doit décrire précisément l’activité principale de cet établissement.', 'Vérifier la catégorie', 'fr'),
    contacts: action((provider) => `Complétez les contacts dans ${provider}`, 'Le client doit comprendre immédiatement comment contacter cet établissement.', 'Vérifier les contacts', 'fr'),
    schedule: action((provider) => `Précisez les horaires dans ${provider}`, 'Des horaires à jour réduisent le risque de visite perdue.', 'Vérifier les horaires', 'fr'),
    action_path: action((provider) => `Ajoutez un parcours de contact clair dans ${provider}`, 'Le téléphone, le site ou la réservation doivent mener à cet établissement et fonctionner sans étapes inutiles.', 'Vérifier la réservation', 'fr'),
    services: action((provider) => `Publiez les principaux services dans ${provider}`, 'La fiche ne permet pas encore de comprendre clairement ce que propose l’établissement.', 'Ouvrir les services', 'fr'),
    prices: action((provider) => `Ajoutez les prix dans ${provider}`, 'Un prix ou un repère clair aide à décider avant la prise de contact.', 'Ouvrir les services', 'fr'),
    reviews: action((provider) => `Commencez à recueillir des avis dans ${provider}`, 'La confiance pour cette fiche est encore moins établie que pour des établissements comparables.', 'Ouvrir les avis', 'fr'),
    review_responses: action((provider) => `Répondez aux avis dans ${provider}`, 'La fiche contient des avis sans réponse.', 'Ouvrir les avis', 'fr'),
    photos: action((provider) => `Ajoutez des photos utiles dans ${provider}`, 'Montrez l’entrée, l’espace, l’équipe, le processus et le résultat pour faciliter le choix du client.', 'Ouvrir les photos', 'fr'),
    publications: action((provider) => `Préparez une publication actuelle pour ${provider}`, 'La publication doit donner une raison concrète de prendre contact maintenant ; elle ne remplace pas une fiche complète.', 'Ouvrir le contenu', 'fr'),
  },
  de: {
    refresh: action((provider) => `Daten bei ${provider} aktualisieren`, 'Für die Wahl der ersten Korrektur wird eine aktuelle Eintragsaufnahme benötigt.', 'Daten aktualisieren', 'de'),
    restore: action((provider) => `Aktualisierung bei ${provider} wiederherstellen`, 'Die letzte Aktualisierung ist fehlgeschlagen. Stellen Sie zuerst die Quelle wieder her.', 'Verbindung prüfen', 'de'),
    add_provider: action(() => 'Plattform zur Prüfung hinzufügen', 'LocalOS weiß noch nicht, welche Einträge zu diesem Standort gehören. Fügen Sie Google, Yandex oder 2GIS hinzu, um eine erste Aufnahme zu erhalten.', 'Plattform hinzufügen', 'de'),
    blocked: action((provider) => `Aktualisierung bei ${provider} wiederherstellen`, 'Die Plattform liefert vorübergehend keine verlässlichen Daten. Stellen Sie zuerst die Quelle wieder her.', 'Verbindung prüfen', 'de'),
    access: action((provider) => `Eintrag bei ${provider} verbinden`, 'Ohne Verbindung kann LocalOS den Eintrag nicht prüfen und das Ergebnis nicht verfolgen.', 'Plattform hinzufügen', 'de'),
    verified: action((provider) => `Verwaltung des Eintrags bei ${provider} prüfen`, 'Die Plattform bestätigt nicht, dass der Eintrag vom Unternehmen verwaltet wird.', 'Eintrag öffnen', 'de'),
    duplicate: action((provider) => `Dubletten bei ${provider} prüfen`, 'Eine Dublette kann Bewertungen aufteilen und Kundinnen und Kunden irreführen.', 'Eintrag prüfen', 'de'),
    category: action((provider) => `Hauptkategorie bei ${provider} präzisieren`, 'Die Kategorie muss die Haupttätigkeit dieses Standorts genau beschreiben.', 'Kategorie prüfen', 'de'),
    contacts: action((provider) => `Kontaktdaten bei ${provider} ergänzen`, 'Kundinnen und Kunden müssen sofort verstehen, wie sie diesen Standort erreichen.', 'Kontakte prüfen', 'de'),
    schedule: action((provider) => `Öffnungszeiten bei ${provider} präzisieren`, 'Aktuelle Öffnungszeiten verringern das Risiko eines verlorenen Besuchs.', 'Öffnungszeiten prüfen', 'de'),
    action_path: action((provider) => `Einen klaren Kontaktweg bei ${provider} hinzufügen`, 'Telefon, Website oder Buchung müssen zu diesem Standort führen und ohne unnötige Schritte funktionieren.', 'Buchung prüfen', 'de'),
    services: action((provider) => `Wichtigste Leistungen bei ${provider} veröffentlichen`, 'Aus dem Eintrag ist noch nicht zuverlässig erkennbar, was das Unternehmen anbietet.', 'Leistungen öffnen', 'de'),
    prices: action((provider) => `Preise bei ${provider} hinzufügen`, 'Ein Preis oder eine klare Orientierung hilft bei der Entscheidung vor der Kontaktaufnahme.', 'Leistungen öffnen', 'de'),
    reviews: action((provider) => `Systematisch Bewertungen bei ${provider} sammeln`, 'Das Vertrauen in diesen Eintrag ist bislang schwächer belegt als bei vergleichbaren Unternehmen.', 'Bewertungen öffnen', 'de'),
    review_responses: action((provider) => `Auf Bewertungen bei ${provider} antworten`, 'Im Eintrag gibt es unbeantwortete Bewertungen.', 'Bewertungen öffnen', 'de'),
    photos: action((provider) => `Nützliche Fotos bei ${provider} hinzufügen`, 'Zeigen Sie Eingang, Räume, Team, Ablauf und Ergebnis, damit Kundinnen und Kunden leichter wählen können.', 'Fotos öffnen', 'de'),
    publications: action((provider) => `Eine aktuelle Veröffentlichung für ${provider} vorbereiten`, 'Die Veröffentlichung soll einen konkreten Anlass zur Kontaktaufnahme geben; sie ersetzt nicht das Ausfüllen des Eintrags.', 'Inhalte öffnen', 'de'),
  },
  tr: {
    refresh: action((provider) => `${provider} verilerini güncelleyin`, 'İlk düzeltmeyi seçmek için kartın güncel bir anlık görüntüsü gerekir.', 'Verileri güncelle', 'tr'),
    restore: action((provider) => `${provider} güncellemesini geri yükleyin`, 'Son güncelleme başarısız oldu. Önce kaynağı geri yükleyin.', 'Bağlantıyı kontrol et', 'tr'),
    add_provider: action(() => 'Kontrol için platform ekleyin', 'LocalOS henüz hangi kartların bu işletmeye ait olduğunu bilmiyor. İlk anlık görüntüyü almak için Google, Yandex veya 2GIS ekleyin.', 'Platform ekle', 'tr'),
    blocked: action((provider) => `${provider} güncellemesini geri yükleyin`, 'Platform geçici olarak güvenilir veri sağlamıyor. Önce kaynağı geri yükleyin.', 'Bağlantıyı kontrol et', 'tr'),
    access: action((provider) => `${provider} kartını bağlayın`, 'Bağlantı olmadan LocalOS kartı kontrol edemez ve sonucu takip edemez.', 'Platform ekle', 'tr'),
    verified: action((provider) => `${provider} kartının yönetimini kontrol edin`, 'Platform, kartın işletme tarafından yönetildiğini doğrulamıyor.', 'Kartı aç', 'tr'),
    duplicate: action((provider) => `${provider} içindeki yinelenen kartları kontrol edin`, 'Yinelenen bir kart yorumları bölebilir ve müşterileri yanıltabilir.', 'Kartı kontrol et', 'tr'),
    category: action((provider) => `${provider} içindeki ana kategoriyi netleştirin`, 'Kategori bu işletmenin ana faaliyetini doğru biçimde açıklamalıdır.', 'Kategoriyi kontrol et', 'tr'),
    contacts: action((provider) => `${provider} içindeki iletişim bilgilerini tamamlayın`, 'Müşteri bu işletmeyle nasıl iletişim kuracağını hemen anlamalıdır.', 'İletişim bilgilerini kontrol et', 'tr'),
    schedule: action((provider) => `${provider} çalışma saatlerini netleştirin`, 'Güncel çalışma saatleri boşa giden ziyaret riskini azaltır.', 'Çalışma saatlerini kontrol et', 'tr'),
    action_path: action((provider) => `${provider} için açık bir iletişim yolu ekleyin`, 'Telefon, web sitesi veya rezervasyon bu işletmeye yönlendirmeli ve gereksiz adımlar olmadan çalışmalıdır.', 'Rezervasyonu kontrol et', 'tr'),
    services: action((provider) => `${provider} içinde temel hizmetleri yayınlayın`, 'Karttan işletmenin tam olarak ne sunduğu henüz güvenle anlaşılamıyor.', 'Hizmetleri aç', 'tr'),
    prices: action((provider) => `${provider} içine fiyat ekleyin`, 'Fiyat veya açık bir referans, iletişimden önce karar vermeye yardımcı olur.', 'Hizmetleri aç', 'tr'),
    reviews: action((provider) => `${provider} üzerinde düzenli yorum toplamaya başlayın`, 'Bu karttaki güven, benzer işletmelere kıyasla henüz daha zayıf doğrulanıyor.', 'Yorumları aç', 'tr'),
    review_responses: action((provider) => `${provider} yorumlarını yanıtlayın`, 'Kartta yanıtsız yorumlar var.', 'Yorumları aç', 'tr'),
    photos: action((provider) => `${provider} için faydalı fotoğraflar ekleyin`, 'Müşterinin daha kolay seçim yapması için girişi, mekânı, ekibi, süreci ve sonucu gösterin.', 'Fotoğrafları aç', 'tr'),
    publications: action((provider) => `${provider} için güncel bir yayın hazırlayın`, 'Yayın, şimdi iletişime geçmek için somut bir neden sunmalıdır; kartı doldurmanın yerini tutmaz.', 'İçeriği aç', 'tr'),
  },
};

const refreshOutcomes = {
  fr: 'Obtenir un état fiable de la fiche et choisir la première correction.',
  de: 'Einen verlässlichen Eintragsstatus erhalten und die erste Korrektur wählen.',
  tr: 'Kartın güvenilir durumunu alın ve ilk düzeltmeyi seçin.',
};

const addProviderOutcomes = {
  fr: 'Obtenir des données récentes de la fiche et déterminer la première correction.',
  de: 'Aktuelle Eintragsdaten erhalten und die erste Korrektur bestimmen.',
  tr: 'Kartın güncel verilerini alın ve ilk düzeltmeyi belirleyin.',
};

const actionMessage = (language: EuropeanLanguage, code: ManagedCardGrowthActionCode): ManagedCardGrowthActionCopy => {
  const item = actionTexts[language][code];
  return {
    title: item.title,
    reason: item.reason,
    cta: item.cta,
    outcome: (goal) => code === 'add_provider'
      ? addProviderOutcomes[language]
      : code === 'refresh' || code === 'restore'
        ? refreshOutcomes[language]
        : Object.prototype.hasOwnProperty.call(goals[language], goal)
          ? goals[language][goal]
          : refreshOutcomes[language],
  };
};

const messagesFor = (language: EuropeanLanguage): Record<ManagedCardGrowthActionCode, ManagedCardGrowthActionCopy> => ({
  refresh: actionMessage(language, 'refresh'), restore: actionMessage(language, 'restore'), add_provider: actionMessage(language, 'add_provider'), blocked: actionMessage(language, 'blocked'), access: actionMessage(language, 'access'), verified: actionMessage(language, 'verified'), duplicate: actionMessage(language, 'duplicate'), category: actionMessage(language, 'category'), contacts: actionMessage(language, 'contacts'), schedule: actionMessage(language, 'schedule'), action_path: actionMessage(language, 'action_path'), services: actionMessage(language, 'services'), prices: actionMessage(language, 'prices'), reviews: actionMessage(language, 'reviews'), review_responses: actionMessage(language, 'review_responses'), photos: actionMessage(language, 'photos'), publications: actionMessage(language, 'publications'),
});

export const managedCardGrowthCopyEuropean: Record<EuropeanLanguage, ManagedCardGrowthCopy> = {
  fr: {
    eyebrow: 'Gestion des fiches', title: 'Objectif et état des fiches', description: 'LocalOS vérifie les plateformes dans l’ordre : d’abord l’accès et l’exactitude de la fiche, puis le contact, l’offre, la confiance, les photos et les raisons actuelles d’agir.', goal: 'Objectif', chooseGoal: 'Choisissez un objectif', saving: 'Enregistrement…', confirmGoal: 'Confirmer l’objectif', goalConfirmed: 'Objectif confirmé. La prochaine étape est choisie en fonction de lui.', networkGoal: 'Confirmez l’objectif séparément pour chaque établissement du réseau.', saveError: 'Impossible d’enregistrer l’objectif', waitingUntil: (date) => `En attente de données jusqu’au ${date}`, waitingDescription: 'La modification est déjà appliquée. À la date de contrôle, LocalOS comparera les actions sur la fiche avec la base de 28 jours.', baseline: 'Base de 28 jours', views: 'Vues', clicks: 'Clics', actions: 'Actions', baselineDisclaimer: 'Les vues et les clics ne sont pas des clients ni des ventes confirmés.', result: 'Résultat de la vérification', resultDisclaimer: 'Les actions sur la plateforme ne sont pas des clients, des commandes ou des ventes confirmés.', critical: 'Un blocage critique existe', noCritical: 'Aucun blocage critique détecté', needsAttention: 'Attention requise', snapshot: (date) => `Capture : ${date}`, sourceObserved: 'Données reçues', sourceBlocked: 'Source indisponible', sourceUnknown: 'Une nouvelle capture est nécessaire', benchmark: (count, days) => `Référence : ${count} établissements comparables, données de moins de ${days} jours.`, smallSample: ' L’échantillon compte moins de 10 établissements.', median: 'médiane', upperQuartile: 'quartile supérieur', benchmarkDisclaimer: 'La comparaison est un repère, pas une preuve de la cause du résultat.', noProviders: 'Aucune plateforme n’a encore été ajoutée. Connectez Google, Yandex ou 2GIS et collectez une capture récente.', noCardState: 'L’état des fiches n’a pas encore été reçu.', nextSteps: 'Prochaines étapes', nextStepsDescription: 'Elles deviendront prioritaires seulement après la fin de l’étape en cours et la vérification des données.', policyVersion: 'Version de la politique', policyUnknown: 'non indiquée', openEvidence: 'Ouvrir les preuves de l’audit', dateUnknown: 'date indisponible', actionHeading: 'Action principale', actionDescription: 'Effectuez d’abord cette étape. LocalOS attendra ensuite la date de contrôle et comparera le résultat.', expectedOutcome: 'Résultat attendu', continue: 'Continuer', auditState: 'État par plateforme', auditDescription: 'Chaque conclusion est liée à une source et à une date de capture. Les données inconnues ne sont pas considérées comme absentes.', source: 'Source', snapshotMissing: 'non reçue', safeFallback: 'Ouvrez la fiche pour vérifier l’étape suivante.', goals: { inquiries: 'Plus de demandes', bookings: 'Plus de réservations', orders: 'Plus de commandes', directions: 'Plus d’itinéraires', website_visits: 'Plus de visites du site' }, gates: { 0: 'Données disponibles', 1: 'La fiche est correcte', 2: 'Les clients peuvent contacter', 3: 'L’offre est claire', 4: 'La confiance est présente', 5: 'Des preuves sont présentes', 6: 'Une raison de revenir existe' }, facts: { access: 'Accès', verified: 'Vérification', duplicate: 'Doublons', category: 'Catégorie', contacts: 'Contacts', schedule: 'Horaires', action_path: 'Parcours de contact', services: 'Services', prices: 'Prix', reviews: 'Avis', review_responses: 'Réponses aux avis', photos: 'Photos', publications: 'Publications' }, states: { observed: 'Vérifié', missing: 'À compléter', unknown: 'Aucune donnée', not_applicable: 'Non applicable', blocked: 'Source indisponible' }, evidence: { connected: 'Fiche connectée', link_missing: 'Aucun lien vers la fiche n’a été ajouté', no_duplicates: 'Aucun doublon détecté', duplicate_unverified: 'La plateforme n’a pas fourni de signal fiable de doublon', internal_contacts: 'Les contacts internes ne prouvent pas leur publication sur la plateforme', internal_schedule: 'Les horaires internes ne prouvent pas que ceux de la plateforme sont à jour', internal_services: 'Les services internes ne prouvent pas leur publication', internal_prices: 'Des prix internes existent, mais la plateforme doit encore être vérifiée', no_organic_news: '2GIS ne dispose pas de canal d’actualités organiques', conversion_content: 'Les publications sont un contenu de conversion, pas un facteur de classement obligatoire', source_error: 'La dernière actualisation de la plateforme a échoué' }, decisions: { insufficient_data: 'Les données comparables de plateforme ne sont pas suffisantes pour évaluer le résultat.', continue: 'Les actions vérifiées sur les fiches ont augmenté par rapport à la période de base.', adjust: 'Il n’y a pas encore de croissance au premier point de contrôle ; la période suivante sera vérifiée.', replace: 'Aucune croissance des actions n’a été enregistrée durant la période de contrôle ; une autre hypothèse est nécessaire.' }, actionMessages: messagesFor('fr'),
  },
  de: {
    eyebrow: 'Eintragsverwaltung', title: 'Ziel und Status der Einträge', description: 'LocalOS prüft Plattformen der Reihe nach: zuerst Zugang und Richtigkeit des Eintrags, dann Kontaktweg, Angebot, Vertrauen, Fotos und aktuelle Handlungsanlässe.', goal: 'Ziel', chooseGoal: 'Ziel auswählen', saving: 'Speichern…', confirmGoal: 'Ziel bestätigen', goalConfirmed: 'Ziel bestätigt. Der nächste Schritt wird daran ausgerichtet.', networkGoal: 'Bestätigen Sie das Ziel für jeden Standort im Netzwerk separat.', saveError: 'Ziel konnte nicht gespeichert werden', waitingUntil: (date) => `Warten auf Daten bis ${date}`, waitingDescription: 'Die Änderung ist bereits umgesetzt. Am Kontrolltag vergleicht LocalOS die Eintragsaktionen mit der 28-Tage-Basis.', baseline: '28-Tage-Basis', views: 'Aufrufe', clicks: 'Klicks', actions: 'Aktionen', baselineDisclaimer: 'Aufrufe und Klicks sind keine bestätigten Kunden oder Verkäufe.', result: 'Prüfergebnis', resultDisclaimer: 'Plattformaktionen sind keine bestätigten Kunden, Bestellungen oder Verkäufe.', critical: 'Es gibt einen kritischen Blocker', noCritical: 'Keine kritischen Blocker gefunden', needsAttention: 'Aufmerksamkeit erforderlich', snapshot: (date) => `Aufnahme: ${date}`, sourceObserved: 'Daten erhalten', sourceBlocked: 'Quelle nicht verfügbar', sourceUnknown: 'Eine neue Aufnahme wird benötigt', benchmark: (count, days) => `Referenz: ${count} vergleichbare Unternehmen, Daten nicht älter als ${days} Tage.`, smallSample: ' Die Stichprobe umfasst weniger als 10 Unternehmen.', median: 'Median', upperQuartile: 'oberes Quartil', benchmarkDisclaimer: 'Der Vergleich ist ein Richtwert, kein Beweis für die Ursache des Ergebnisses.', noProviders: 'Es wurden noch keine Plattformen hinzugefügt. Verbinden Sie Google, Yandex oder 2GIS und erfassen Sie eine aktuelle Aufnahme.', noCardState: 'Der Status der Einträge wurde noch nicht empfangen.', nextSteps: 'Nächste Schritte', nextStepsDescription: 'Sie werden erst nach Abschluss des aktuellen Schritts und Prüfung der Daten vorrangig.', policyVersion: 'Regelversion', policyUnknown: 'nicht angegeben', openEvidence: 'Auditnachweise öffnen', dateUnknown: 'Datum nicht verfügbar', actionHeading: 'Wichtigste Aktion', actionDescription: 'Führen Sie zuerst diesen Schritt aus. Anschließend wartet LocalOS auf den Kontrolltag und vergleicht das Ergebnis.', expectedOutcome: 'Erwartetes Ergebnis', continue: 'Weiter', auditState: 'Status nach Plattform', auditDescription: 'Jede Schlussfolgerung ist mit Quelle und Aufnahmedatum verbunden. Unbekannte Daten gelten nicht als fehlend.', source: 'Quelle', snapshotMissing: 'nicht empfangen', safeFallback: 'Öffnen Sie den Eintrag, um den nächsten Schritt zu prüfen.', goals: { inquiries: 'Mehr Anfragen', bookings: 'Mehr Buchungen', orders: 'Mehr Bestellungen', directions: 'Mehr Routen', website_visits: 'Mehr Websitebesuche' }, gates: { 0: 'Daten verfügbar', 1: 'Eintrag ist korrekt', 2: 'Kunden können Kontakt aufnehmen', 3: 'Angebot ist klar', 4: 'Vertrauen ist vorhanden', 5: 'Nachweise sind vorhanden', 6: 'Es gibt einen Grund wiederzukommen' }, facts: { access: 'Zugang', verified: 'Bestätigung', duplicate: 'Dubletten', category: 'Kategorie', contacts: 'Kontakte', schedule: 'Öffnungszeiten', action_path: 'Kontaktweg', services: 'Leistungen', prices: 'Preise', reviews: 'Bewertungen', review_responses: 'Antworten auf Bewertungen', photos: 'Fotos', publications: 'Veröffentlichungen' }, states: { observed: 'Geprüft', missing: 'Zu ergänzen', unknown: 'Keine Daten', not_applicable: 'Nicht zutreffend', blocked: 'Quelle nicht verfügbar' }, evidence: { connected: 'Eintrag verbunden', link_missing: 'Kein Link zum Eintrag wurde hinzugefügt', no_duplicates: 'Keine Dubletten gefunden', duplicate_unverified: 'Die Plattform hat kein verlässliches Dublettensignal geliefert', internal_contacts: 'Interne Kontaktdaten beweisen keine Veröffentlichung auf der Plattform', internal_schedule: 'Interne Öffnungszeiten beweisen nicht, dass die Plattformzeiten aktuell sind', internal_services: 'Interne Leistungen beweisen nicht ihre Veröffentlichung', internal_prices: 'Interne Preise existieren, die Plattform muss aber noch geprüft werden', no_organic_news: '2GIS hat keinen organischen Nachrichtenkanal', conversion_content: 'Veröffentlichungen sind Conversion-Inhalte, kein verpflichtender Rankingfaktor', source_error: 'Die letzte Plattformaktualisierung ist fehlgeschlagen' }, decisions: { insufficient_data: 'Es gibt nicht genug vergleichbare Plattformdaten, um das Ergebnis zu bewerten.', continue: 'Bestätigte Aktionen in den Einträgen sind gegenüber dem Basiszeitraum gestiegen.', adjust: 'Am ersten Kontrollpunkt gibt es noch kein Wachstum; der nächste Zeitraum wird geprüft.', replace: 'Im Kontrollzeitraum wurde kein Aktionswachstum erfasst; eine andere Hypothese ist erforderlich.' }, actionMessages: messagesFor('de'),
  },
  tr: {
    eyebrow: 'İşletme kartı yönetimi', title: 'Kart hedefi ve durumu', description: 'LocalOS platformları sırayla kontrol eder: önce kartın erişimi ve doğruluğu, ardından iletişim yolu, teklif, güven, fotoğraflar ve güncel harekete geçme nedenleri.', goal: 'Hedef', chooseGoal: 'Hedef seçin', saving: 'Kaydediliyor…', confirmGoal: 'Hedefi onayla', goalConfirmed: 'Hedef onaylandı. Sonraki adım buna göre seçilir.', networkGoal: 'Ağdaki her işletme için hedefi ayrı ayrı onaylayın.', saveError: 'Hedef kaydedilemedi', waitingUntil: (date) => `${date} tarihine kadar veri bekleniyor`, waitingDescription: 'Değişiklik zaten uygulandı. Kontrol tarihinde LocalOS kart işlemlerini 28 günlük temel dönemle karşılaştıracak.', baseline: '28 günlük temel dönem', views: 'Görüntülemeler', clicks: 'Tıklamalar', actions: 'İşlemler', baselineDisclaimer: 'Görüntülemeler ve tıklamalar doğrulanmış müşteriler veya satışlar değildir.', result: 'Kontrol sonucu', resultDisclaimer: 'Platform işlemleri doğrulanmış müşteriler, siparişler veya satışlar değildir.', critical: 'Kritik bir engel var', noCritical: 'Kritik engel bulunmadı', needsAttention: 'Dikkat gerekiyor', snapshot: (date) => `Anlık görüntü: ${date}`, sourceObserved: 'Veriler alındı', sourceBlocked: 'Kaynak kullanılamıyor', sourceUnknown: 'Yeni bir anlık görüntü gerekiyor', benchmark: (count, days) => `Referans: ${count} benzer işletme, veriler ${days} günden eski değil.`, smallSample: ' Örneklem 10 işletmenin altında.', median: 'medyan', upperQuartile: 'üst çeyrek', benchmarkDisclaimer: 'Karşılaştırma bir referanstır, sonucun nedeninin kanıtı değildir.', noProviders: 'Henüz hiçbir platform eklenmedi. Google, Yandex veya 2GIS bağlayın ve güncel bir anlık görüntü alın.', noCardState: 'Kartların durumu henüz alınmadı.', nextSteps: 'Sonraki adımlar', nextStepsDescription: 'Yalnızca mevcut adım tamamlanıp veriler kontrol edildikten sonra öncelikli hâle gelirler.', policyVersion: 'Politika sürümü', policyUnknown: 'belirtilmedi', openEvidence: 'Denetim kanıtlarını aç', dateUnknown: 'tarih kullanılamıyor', actionHeading: 'Ana işlem', actionDescription: 'Önce bu adımı tamamlayın. Ardından LocalOS kontrol tarihini bekleyip sonucu karşılaştıracaktır.', expectedOutcome: 'Beklenen sonuç', continue: 'Devam et', auditState: 'Platforma göre durum', auditDescription: 'Her sonuç bir kaynak ve anlık görüntü tarihiyle bağlantılıdır. Bilinmeyen veriler eksik sayılmaz.', source: 'Kaynak', snapshotMissing: 'alınmadı', safeFallback: 'Sonraki adımı kontrol etmek için kartı açın.', goals: { inquiries: 'Daha fazla başvuru', bookings: 'Daha fazla rezervasyon', orders: 'Daha fazla sipariş', directions: 'Daha fazla rota', website_visits: 'Daha fazla web sitesi ziyareti' }, gates: { 0: 'Veriler kullanılabilir', 1: 'Kart doğru', 2: 'Müşteriler iletişime geçebilir', 3: 'Teklif açık', 4: 'Güven var', 5: 'Kanıtlar var', 6: 'Geri dönmek için neden var' }, facts: { access: 'Erişim', verified: 'Doğrulama', duplicate: 'Yinelenen kartlar', category: 'Kategori', contacts: 'İletişim bilgileri', schedule: 'Çalışma saatleri', action_path: 'İletişim yolu', services: 'Hizmetler', prices: 'Fiyatlar', reviews: 'Yorumlar', review_responses: 'Yorum yanıtları', photos: 'Fotoğraflar', publications: 'Yayınlar' }, states: { observed: 'Doğrulandı', missing: 'Tamamlanmalı', unknown: 'Veri yok', not_applicable: 'Uygulanamaz', blocked: 'Kaynak kullanılamıyor' }, evidence: { connected: 'Kart bağlandı', link_missing: 'Karta ait bağlantı eklenmedi', no_duplicates: 'Yinelenen kart bulunmadı', duplicate_unverified: 'Platform güvenilir bir yinelenen kart sinyali vermedi', internal_contacts: 'Dahili iletişim bilgileri bunların platformda yayınlandığını kanıtlamaz', internal_schedule: 'Dahili saatler platform saatlerinin güncel olduğunu kanıtlamaz', internal_services: 'Dahili hizmetler bunların yayınlandığını kanıtlamaz', internal_prices: 'Dahili fiyatlar mevcut, ancak platform hâlâ kontrol edilmeli', no_organic_news: '2GIS organik bir haber kanalına sahip değil', conversion_content: 'Yayınlar, zorunlu sıralama faktörü değil dönüşüm içeriğidir', source_error: 'Son platform güncellemesi başarısız oldu' }, decisions: { insufficient_data: 'Sonucu değerlendirmek için yeterli karşılaştırılabilir platform verisi yok.', continue: 'Kartlardaki doğrulanmış işlemler temel döneme göre arttı.', adjust: 'İlk kontrol noktasında henüz büyüme yok; sonraki dönem kontrol edilecek.', replace: 'Kontrol döneminde işlem artışı kaydedilmedi; farklı bir hipotez gerekiyor.' }, actionMessages: messagesFor('tr'),
  },
};
