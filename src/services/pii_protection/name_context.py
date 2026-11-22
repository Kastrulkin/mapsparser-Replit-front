"""Conservative name spans next to scheduling/contact intent across scripts."""

import re
import unicodedata

from services.pii_protection.engines import Finding


WORD = r"[^\W\d_](?:[^\W\d_]|['’\-\u064b-\u065f\u0670])*"
SEQUENCE = WORD + r"(?:[ \t]+" + WORD + r"){1,5}"
AFTER_NAME = re.compile(
    r"(?P<name>" + SEQUENCE + r")[ \t]+(?:"
    r"would\s+like\s+to|wants\s+to|needs\s+to|requested\s+(?:an?\s+)?appointment|"
    r"просит\s+(?:перенести|записать|отменить)|хочет\s+(?:записаться|перенести)|"
    r"möchte\s+(?:einen\s+)?Termin|randevu(?:sunu)?\s+(?:almak|değiştirmek)|"
    r"(?:ترغب|يرغب|تريد|يريد)\s+(?:في\s+)?(?:حجز|إعادة\s+جدولة|تأجيل))",
    re.I,
)
BEFORE_NAME = re.compile(
    r"(?:\bcall|\bcontact|\bпозвоните|\bсвяжитесь\s+с|\bзапишите|اتصل\s+بـ?)"
    r"[ \t]+(?P<name>" + SEQUENCE + ")", re.I,
)
PARTICLES = {"de", "da", "van", "von", "bin", "al"}
STOPWORDS = {"please", "call", "contact", "customer", "client", "patient", "клиент", "клиенту",
             "пациент", "пожалуйста", "позвоните", "запишите", "العميل", "العميلة", "لطفا",
             "later", "then", "also", "today", "tomorrow", "yesterday", "currently", "finally",
             "затем", "сегодня", "завтра", "потом", "также"}


def name_part(word):
    letters = [character for character in word if character.isalpha()]
    if len(letters) < 2 or word.casefold() in STOPWORDS:
        return False
    return letters[0].isupper() or all("ARABIC" in unicodedata.name(character, "") for character in letters)


def contextual_names(text):
    result = []
    for pattern, suffix in ((AFTER_NAME, True), (BEFORE_NAME, False)):
        for match in pattern.finditer(text):
            words = list(re.finditer(WORD, match.group("name")))
            selected = []
            for word in reversed(words) if suffix else words:
                if not name_part(word.group()) and word.group().casefold() not in PARTICLES:
                    break
                selected.append(word)
            selected.sort(key=lambda word: word.start())
            if len(selected) < 2 or not name_part(selected[0].group()) or not name_part(selected[-1].group()):
                continue
            offset = match.start("name")
            result.append(Finding(offset + selected[0].start(), offset + selected[-1].end(), "PERSON"))
    return result
