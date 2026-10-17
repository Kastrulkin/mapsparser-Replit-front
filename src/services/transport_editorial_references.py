"""Choose passenger-transport references, not mentions in startup reports."""
import re


def is_transport_editorial_reference(text):
    value = str(text or '').casefold()
    if re.search(r'стартап|#новостинедели|unit.?эконом|unit.?рентаб|transferwise|western union|венчур|\bstartup\b|\brealtor|риэлтор|эвакуатор|грузоперевоз', value):
        return False
    return bool(re.search(
        r'аэропорт|трансфер|пассажир|турист|водител|\btaxi\b|\bchauffeur\b|'
        r'\bairport\b|\bpassengers?\b|\btravell?ers?\b|\bsightseeing\b|'
        r'\bpick.?up\b|lufthavn|chauffør|passager|taxakørsel', value))
