"""Request-local planner context. Authorization and execution retain full server data."""
import re

DOMAINS = {
    'content': r'\bпост(?:а|ы|ов|е|у|ом)?\b|контент|публикац|новост',
    'finance': r'выруч|расход|доход|чек|финанс|продаж|возврат',
    'services': r'услуг|прайс|цен[ауы]',
    'reviews': r'отзыв|рейтинг',
    'work': r'журнал|жалоб|недоволь|плохо встрет|сотрудник|заметк|предложени|иде[яию]|допродаж',
    'settings': r'город|валют|часов.{0,10}пояс',
}


class PlannerContext:
    def __init__(self, message):
        self.domains = {name for name, pattern in DOMAINS.items() if re.search(pattern, message, re.I)}
        self.references = {}
        self.reverse = {}

    def tools(self, tools):
        if not self.domains:
            return tools
        selected = [tool for tool in tools if tool['name'].split('.')[0] in self.domains or tool['name'].startswith(('operator.', 'settings.'))]
        return selected or tools

    def encode(self, value):
        if isinstance(value, dict):
            return {key: self.encode(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.encode(item) for item in value]
        if isinstance(value, str) and re.fullmatch(r'[a-fA-F0-9]{64}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}', value):
            if value not in self.reverse:
                ref = '@ref' + str(len(self.references) + 1)
                self.references[ref] = value; self.reverse[value] = ref
            return self.reverse[value]
        return value

    def decode(self, value):
        if isinstance(value, dict): return {key: self.decode(item) for key, item in value.items()}
        if isinstance(value, list): return [self.decode(item) for item in value]
        if isinstance(value, str): return self.references.get(value, value)
        return value

    def history(self, history):
        # Keep recent clarification turns in full; omit older unrelated topics.
        if not self.domains: return history[-6:]
        return [item for index, item in enumerate(history) if any(
            re.search(DOMAINS[domain], item['content'], re.I) for domain in self.domains)][-6:]
