"""Dedicated SpeechKit credentials; no fallback to unrelated Yandex keys."""
import os
import requests


class SpeechKit:
    def __init__(self):
        key = os.getenv('OPERATOR_SPEECHKIT_API_KEY', '').strip()
        if not key:
            raise ValueError('Распознавание речи пока не настроено')
        self.headers = {'Authorization': 'Api-Key ' + key}

    def _json(self, method, url, **kwargs):
        try:
            response = requests.request(method, url, headers=self.headers, timeout=(10, 45), **kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError):
            raise ValueError('Сервис речи временно недоступен') from None

    def start(self, content):
        import base64
        result = self._json('POST', 'https://stt.api.cloud.yandex.net/stt/v3/recognizeFileAsync', json={
            'content': base64.b64encode(content).decode(),
            'recognitionModel': {'model': 'general', 'audioFormat': {'containerAudio': {'containerAudioType': 'OGG_OPUS'}},
                'textNormalization': {'textNormalization': 'TEXT_NORMALIZATION_ENABLED'},
                'languageRestriction': {'restrictionType': 'WHITELIST', 'languageCode': ['ru-RU']},
                'audioProcessingType': 'FULL_DATA'},
        })
        return result['id']

    def result(self, operation_id):
        operation = self._json('GET', 'https://operation.api.cloud.yandex.net/operations/' + operation_id)
        if not operation.get('done'):
            return None
        if operation.get('error'):
            raise ValueError('Не удалось распознать запись. Попробуйте записать ещё раз')
        try:
            response = requests.get('https://stt.api.cloud.yandex.net/stt/v3/getRecognition',
                params={'operationId': operation_id}, headers=self.headers, timeout=(10, 45))
            response.raise_for_status()
            import json
            parts = {}
            for line in response.text.splitlines():
                if not line.strip():
                    continue
                record = json.loads(line)
                item = record.get('result', record)
                refinement = item.get('finalRefinement') or {}
                final = refinement.get('normalizedText') or item.get('final') or {}
                index = str(refinement.get('finalIndex', (item.get('audioCursors') or {}).get('finalIndex', len(parts))))
                alternatives = final.get('alternatives') or []
                if alternatives:
                    parts[index] = alternatives[0].get('text', '')
            return ' '.join(parts.values()).strip()
        except (requests.RequestException, ValueError):
            raise ValueError('Не удалось получить расшифровку') from None

    def synthesize(self, text):
        try:
            response = requests.post('https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize',
                headers=self.headers, data={'text': text[:1000], 'lang': 'ru-RU', 'voice': 'alena', 'format': 'oggopus'}, timeout=(10, 45))
            response.raise_for_status()
            return response.content
        except requests.RequestException:
            raise ValueError('Озвучивание временно недоступно. Текст ответа сохранён') from None
