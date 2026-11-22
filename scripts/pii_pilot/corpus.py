"""Frozen synthetic evaluation corpus; no database, network or customer inputs."""

import hashlib
import json
from pathlib import Path


LANGUAGES = ("ru", "ru", "ru", "en", "en", "tr", "tr", "de", "ar", "mixed")
NAMES = {
    "ru": "Ирина Примерова", "en": "Mira Exampleton", "tr": "Deniz Örneksoy",
    "de": "Mira Beispielmann", "ar": "مريم التجريبية", "mixed": "Ирина Exampleton",
}
LABELS = {
    "ru": ("ФИО", "Телефон", "Адрес", "Паспорт", "Клиент", "Организация"),
    "en": ("Full name", "Phone", "Home address", "Passport", "Customer", "Organization"),
    "tr": ("Ad soyad", "Telefon", "Ev adresi", "Pasaport", "Müşteri", "Şirket"),
    "de": ("Name", "Telefon", "Privatadresse", "Reisepass", "Kunde", "Organisation"),
    "ar": ("الاسم", "الهاتف", "العنوان", "جواز السفر", "العميل", "الشركة"),
    "mixed": ("ФИО", "Phone", "Ev adresi", "Passport", "Customer", "Şirket"),
}
KINDS = (
    "labeled_name", "free_name", "phone", "email", "home_address", "passport",
    "card", "bank_account", "customer_order", "api_secret", "password",
    "private_organization", "mixed_record", "html", "json", "obfuscated",
    "unicode", "public_geo", "negative_numbers", "initials_typo",
)
CRITICAL = {"PHONE", "EMAIL", "PASSPORT", "BANK", "SECRET"}


def scenarios():
    """Generate exactly 200 cases from 20 forms and ten language/format variants."""
    cases = []
    for kind_index, kind in enumerate(KINDS):
        for variant, language in enumerate(LANGUAGES):
            index = kind_index * 10 + variant
            name = NAMES[language]
            labels = LABELS[language]
            phone = ("+7 (999) 000-01-%02d" % variant if language == "ru" else
                     "+90 555 000 01 %02d" % variant if language == "tr" else
                     "+49 151 0000 01%02d" % variant if language == "de" else
                     "+971 50 000 01%02d" % variant if language == "ar" else
                     "+1 (202) 555-01%02d" % variant)
            email = f"person{index}@example.invalid"
            address = {
                "ru": f"ул. Синтетическая, д. {index + 1}, кв. 7",
                "en": f"{index + 1} Example Lane, Apt 7",
                "tr": f"Örnek Mahallesi, Test Sokak {index + 1}, Daire 7",
                "de": f"Beispielstraße {index + 1}, Wohnung 7",
                "ar": f"شارع الاختبار {index + 1} شقة 7",
                "mixed": f"ул. Example, дом {index + 1}, Daire 7",
            }[language]
            text = ""
            entities = []
            allowed = []

            def literal(value):
                nonlocal text
                text += value

            def entity(value, entity_type):
                nonlocal text
                start = len(text)
                text += value
                entities.append({"start": start, "end": len(text), "type": entity_type,
                                 "value": value, "critical": entity_type in CRITICAL})

            literal({"ru": "Тестовая запись. ", "en": "Synthetic record. ",
                     "tr": "Sentetik kayıt. ", "de": "Synthetischer Eintrag. ",
                     "ar": "سجل تجريبي. ", "mixed": "Тестовая запись / synthetic kayıt. "}[language])
            if kind == "labeled_name":
                literal(labels[0] + ": ")
                entity(name, "PERSON")
            elif kind == "free_name":
                if language == "ru":
                    literal("Позвоните ")
                    entity("Ирине Примеровой", "PERSON")
                    literal(" после приёма.")
                else:
                    entity(name, "PERSON")
                    literal(" would like to reschedule the appointment.")
            elif kind == "phone":
                literal(labels[1] + ": ")
                entity(phone, "PHONE")
            elif kind == "email":
                literal("Email: ")
                entity(email, "EMAIL")
            elif kind == "home_address":
                literal(labels[2] + ": ")
                entity(address, "ADDRESS")
            elif kind == "passport":
                literal(labels[3] + ": ")
                entity(f"TEST{index:06d}" if language != "ru" else f"00 00 {index:06d}", "PASSPORT")
            elif kind == "card":
                literal("Card number: ")
                entity("4111 1111 1111 1111", "BANK")
            elif kind == "bank_account":
                literal("IBAN: ")
                entity("GB82 WEST 1234 5698 7654 32", "BANK")
                literal("; bank_account: ")
                entity(f"0000000000000000{index:04d}", "BANK")
            elif kind == "customer_order":
                literal("customer_id: ")
                entity(f"SYNTH-C{index:05d}", "IDENTIFIER")
                literal("; order_id: ")
                entity(f"SYNTH-O{index:05d}", "IDENTIFIER")
            elif kind == "api_secret":
                literal("api_key: ")
                entity(f"synthetic_only_not_a_credential_{index:06d}", "SECRET")
            elif kind == "password":
                literal("Пароль: " if language == "ru" else "password: ")
                entity(f"Synthetic!Only{index}#", "SECRET")
            elif kind == "private_organization":
                literal(labels[5] + ": ")
                entity(f"Example Private Company {index}", "ORGANIZATION")
            elif kind == "mixed_record":
                literal(labels[0] + ": ")
                entity(name, "PERSON")
                literal("; email: ")
                entity(email, "EMAIL")
                literal("; " + labels[1] + ": ")
                entity(phone, "PHONE")
                literal("; " + labels[2] + ": ")
                entity(address, "ADDRESS")
            elif kind == "html":
                literal('<div data-note="synthetic"><b>Email:</b> ')
                entity(email, "EMAIL")
                literal("<br>" + labels[1] + ": ")
                entity(phone, "PHONE")
                literal("</div>")
            elif kind == "json":
                literal('{"customer_name":"')
                entity(name, "PERSON")
                literal('","email":"')
                entity(email, "EMAIL")
                literal('","phone":"')
                entity(phone, "PHONE")
                literal('"}')
            elif kind == "obfuscated":
                literal("Email: ")
                entity(f"person{index} [at] example [dot] invalid", "EMAIL")
                literal("; phone: ")
                entity(f"+7·999·000·01·{variant:02d}", "PHONE")
            elif kind == "unicode":
                literal("Email: ")
                entity(f"person{index}\u200b@example.invalid", "EMAIL")
                literal("; phone: ")
                entity("＋７ ９９９ ０００ ０１ " + str(variant).zfill(2).translate(str.maketrans("0123456789", "０１２３４５６７８９")), "PHONE")
            elif kind == "public_geo":
                public_name = f"Example Studio {index}"
                public_address = f"Example Commercial Avenue {index}"
                literal(f"Company: {public_name}; business_address: {public_address}; service: haircut")
                allowed = [public_name, public_address]
            elif kind == "negative_numbers":
                literal("Services: haircut 1500 RUB; discount 10%; rating 4.8; 32 reviews; 10:30–19:00; 2026-11-01")
            else:
                literal("ФИО: " if language == "ru" else labels[0] + ": ")
                entity("И. П. Примерова" if language == "ru" else name.replace(" ", "  "), "PERSON")
                literal("; emial: ")
                entity(email, "EMAIL")
            for item in entities:
                assert text[item["start"]:item["end"]] == item["value"]
            cases.append({"id": f"synthetic-{index:03d}", "language": language,
                          "kind": kind, "policy": "public_geo" if kind == "public_geo" else "private",
                          "text": text, "entities": entities, "allowed_public": allowed})
    assert len(cases) == 200
    return cases


def write_corpus(path):
    content = "".join(json.dumps(case, ensure_ascii=False, sort_keys=True) + "\n" for case in scenarios())
    Path(path).write_text(content, encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


if __name__ == "__main__":
    import sys
    print(write_corpus(sys.argv[1]))
