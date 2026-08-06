import type { Language } from './LanguageContext';

type DemoShowcaseText = {
  service: string;
  serviceDescription: string;
  keyword: string;
  review: string;
  reply: string;
  newsTitle: string;
  newsText: string;
  competitor: string;
};

const textByLanguage: Record<Language, DemoShowcaseText> = {
  ru: { service: 'Стрижка собак', serviceDescription: 'Аккуратная стрижка и уход за шерстью.', keyword: 'груминг собак', review: 'Демо-отзыв о груминге, внимательности мастера и удобной записи.', reply: 'Спасибо за отзыв! Рады, что вам понравились работа мастера и удобная запись.', newsTitle: 'Летний уход за питомцем', newsText: 'Подготовили памятку по уходу за шерстью в жаркую погоду.', competitor: 'Пушистый стиль' },
  en: { service: 'Dog grooming', serviceDescription: 'Careful grooming and coat care.', keyword: 'dog grooming', review: 'A demo review about grooming, the specialist’s care, and easy booking.', reply: 'Thank you! We are glad you appreciated the specialist’s care and easy booking.', newsTitle: 'Summer pet care', newsText: 'A practical guide to coat care in hot weather.', competitor: 'Fluffy Style' },
  fr: { service: 'Toilettage pour chiens', serviceDescription: 'Toilettage soigné et entretien du pelage.', keyword: 'toilettage chien', review: 'Avis de démonstration sur le toilettage, l’attention du spécialiste et la réservation facile.', reply: 'Merci ! Nous sommes ravis que vous ayez apprécié le soin et la réservation simple.', newsTitle: 'Soins d’été pour animaux', newsText: 'Un guide pratique pour entretenir le pelage par temps chaud.', competitor: 'Style Douillet' },
  es: { service: 'Peluquería canina', serviceDescription: 'Corte cuidadoso y cuidado del pelaje.', keyword: 'peluquería canina', review: 'Reseña de demostración sobre el cuidado, la atención del especialista y la reserva sencilla.', reply: '¡Gracias! Nos alegra que valoraras la atención y la facilidad de reserva.', newsTitle: 'Cuidados de verano para mascotas', newsText: 'Una guía práctica para cuidar el pelaje cuando hace calor.', competitor: 'Estilo Peludo' },
  el: { service: 'Κούρεμα σκύλων', serviceDescription: 'Προσεκτικό κούρεμα και περιποίηση τριχώματος.', keyword: 'περιποίηση σκύλων', review: 'Κριτική επίδειξης για την περιποίηση, την προσοχή του ειδικού και την εύκολη κράτηση.', reply: 'Ευχαριστούμε! Χαιρόμαστε που εκτιμήσατε τη φροντίδα και την εύκολη κράτηση.', newsTitle: 'Καλοκαιρινή φροντίδα κατοικιδίων', newsText: 'Ένας πρακτικός οδηγός για τη φροντίδα του τριχώματος στη ζέστη.', competitor: 'Χνουδωτό Στυλ' },
  de: { service: 'Hundefellpflege', serviceDescription: 'Sorgfältiger Schnitt und professionelle Fellpflege.', keyword: 'hundefellpflege', review: 'Demo-Bewertung zu Pflege, Aufmerksamkeit des Teams und einfacher Terminbuchung.', reply: 'Vielen Dank! Wir freuen uns, dass Ihnen die Betreuung und einfache Buchung gefallen haben.', newsTitle: 'Sommerpflege für Haustiere', newsText: 'Ein praktischer Leitfaden zur Fellpflege bei warmem Wetter.', competitor: 'Flauschiger Stil' },
  th: { service: 'ตัดแต่งขนสุนัข', serviceDescription: 'ตัดแต่งและดูแลขนอย่างพิถีพิถัน', keyword: 'ตัดขนสุนัข', review: 'รีวิวตัวอย่างเกี่ยวกับการดูแล ความใส่ใจของผู้เชี่ยวชาญ และการจองที่สะดวก', reply: 'ขอบคุณค่ะ เรายินดีที่คุณประทับใจกับการดูแลและการจองที่สะดวก', newsTitle: 'การดูแลสัตว์เลี้ยงช่วงหน้าร้อน', newsText: 'คำแนะนำง่าย ๆ สำหรับดูแลขนสัตว์เลี้ยงในวันที่อากาศร้อน', competitor: 'สไตล์ขนนุ่ม' },
  ar: { service: 'العناية بشعر الكلاب', serviceDescription: 'قص دقيق وعناية احترافية بالشعر.', keyword: 'العناية بالكلاب', review: 'مراجعة تجريبية عن العناية واهتمام المختص وسهولة الحجز.', reply: 'شكرًا لك! يسعدنا أنك قدّرت العناية وسهولة الحجز.', newsTitle: 'العناية بالحيوانات صيفًا', newsText: 'دليل عملي للعناية بالشعر في الطقس الحار.', competitor: 'أسلوب ناعم' },
  ha: { service: 'Gyaran gashin kare', serviceDescription: 'Gyara da kula da gashi cikin ƙwarewa.', keyword: 'gyaran kare', review: 'Sharhin demo game da kulawa, ƙwarewar ma’aikaci da sauƙin yin booking.', reply: 'Mun gode! Muna farin ciki da kuka ji daɗin kulawa da sauƙin booking.', newsTitle: 'Kula da dabba a lokacin zafi', newsText: 'Jagora mai amfani don kula da gashi a yanayin zafi.', competitor: 'Salon Gashi Mai Laushi' },
  tr: { service: 'Köpek tıraşı', serviceDescription: 'Özenli tıraş ve tüy bakımı.', keyword: 'köpek bakımı', review: 'Bakım, uzmanın ilgisi ve kolay randevu hakkında demo yorumu.', reply: 'Teşekkür ederiz! İlgi ve kolay randevudan memnun kalmanıza sevindik.', newsTitle: 'Yaz aylarında evcil hayvan bakımı', newsText: 'Sıcak havalarda tüy bakımı için pratik bir rehber.', competitor: 'Pofuduk Stil' },
};

export const getDemoShowcaseData = (language: Language) => {
  const text = textByLanguage[language];
  const date = '2026-06-20T12:00:00Z';
  const competitorNames = [text.competitor, `${text.competitor} 2`, `${text.competitor} 3`, `${text.competitor} 4`];
  return {
    services: [{ id: `demo-service-${language}`, name: text.service, description: text.serviceDescription, keywords: [text.keyword], seo_keywords: [text.keyword], price: 1500, currency: 'RUB', source: 'yandex', updated_at: date, is_active: true }],
    reviews: [{ id: `demo-review-${language}`, source: 'yandex', rating: 5, author_name: language === 'ru' ? 'Сергей Новиков' : 'Demo customer', text: text.review, response_text: text.reply, published_at: date, has_response: true, reply_draft_id: null, reply_draft_text: text.reply, reply_draft_status: 'draft', location_name: 'Roga i Kopyta' }],
    news: [{ id: `demo-news-${language}`, title: text.newsTitle, text: text.newsText, content: text.newsText, status: 'draft', created_at: date, published_at: null, source: 'LocalOS' }],
    keywords: [{ keyword: text.keyword, views: 420, category: text.service, updated_at: date }],
    competitors: [{ id: `demo-competitor-${language}`, name: text.competitor, title: text.competitor, rating: 4.4, reviews_count: 72 }],
    manualCompetitors: competitorNames.map((name, index) => ({
      id: `demo-manual-competitor-${language}-${index + 1}`,
      name,
      url: `https://yandex.example/demo-competitor-${language}-${index + 1}`,
      audit_status: 'not_requested',
    })),
  };
};
