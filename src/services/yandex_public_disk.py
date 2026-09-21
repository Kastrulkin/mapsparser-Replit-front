"""Read only the public folder explicitly supplied by a business owner."""
import re
from urllib.parse import urlparse, quote, urljoin
import requests
from services import yandex_disk
from services.disk_import_providers import checked, bounded_download, kind, numeric, AccessLost

IDENTITY = 'yandex_public_folder_v1'
PRIVATE_DIRECTORIES = {"driver's licenses"}


def folder_url(value):
    if not isinstance(value, str):
        raise ValueError('Вставьте публичную ссылку на папку Яндекс Диска.')
    parsed = urlparse(value)
    if (parsed.scheme != 'https' or parsed.hostname not in {'disk.360.yandex.ru', 'disk.yandex.ru', 'yadi.sk'}
            or parsed.username or parsed.password or parsed.port not in {None, 443}
            or not re.fullmatch(r'/d/[A-Za-z0-9_-]+/?', parsed.path)):
        raise ValueError('Нужна публичная ссылка Яндекс Диска вида https://disk.yandex.ru/d/…')
    return 'https://' + parsed.hostname + parsed.path.rstrip('/')


class PublicReader:
    def __init__(self, cursor, source):
        self.source = source
        self.url = folder_url(source['root_url'])

    def path(self, value):
        if not isinstance(value, str) or not value.startswith('/') or any(part in {'.', '..'} for part in value.split('/')):
            raise ValueError('Неверный путь внутри папки.')
        if any(part.casefold() in PRIVATE_DIRECTORIES for part in value.split('/')):
            raise ValueError('Папка с личными документами исключена из контента.')
        return value

    def metadata(self, path='/'):
        return checked(requests.get(yandex_disk.API + '/public/resources', params={
            'public_key': self.url, 'path': self.path(path), 'limit': 0,
            'fields': 'name,type,path,resource_id,sha256,md5,modified,size,mime_type'}, timeout=(10, 30)))

    def page(self, folder, token=None):
        body = checked(requests.get(yandex_disk.API + '/public/resources', params={
            'public_key': self.url, 'path': self.path(folder), 'offset': token or 0, 'limit': 100, 'sort': 'name',
            'fields': 'type,_embedded.offset,_embedded.total,_embedded.items.name,_embedded.items.type,_embedded.items.path,_embedded.items.resource_id,_embedded.items.sha256,_embedded.items.md5,_embedded.items.modified,_embedded.items.size,_embedded.items.mime_type'}, timeout=(10, 30)))
        embedded = body.get('_embedded')
        if body.get('type') != 'dir' or not isinstance(embedded, dict) or not isinstance(embedded.get('items'), list):
            raise AccessLost('Публичная папка недоступна.')
        offset = embedded.get('offset')
        total = embedded.get('total')
        if not isinstance(offset, int) or not isinstance(total, int) or offset != (token or 0):
            raise ValueError('Диск вернул неполную страницу.')
        rows = embedded['items']
        continuation = offset + len(rows)
        if continuation < total and not rows:
            raise ValueError('Диск вернул незавершённую страницу.')
        return [self.normalize(row) for row in rows], continuation if continuation < total else None

    def normalize(self, row):
        identifier = row.get('resource_id')
        if not identifier:
            raise ValueError('Диск не вернул постоянный идентификатор файла.')
        path = row['path']
        private = any(part.casefold() in PRIVATE_DIRECTORIES for part in path.split('/'))
        if not private: self.path(path)
        mime = row.get('mime_type', '')
        return {'id': identifier, 'path': path, 'name': row['name'], 'mime_type': mime,
                'kind': 'unsupported' if private else 'folder' if row.get('type') == 'dir' else kind(mime, row['name']),
                'skip_reason': 'Папка с личными документами исключена' if private else 'unsupported_format',
                'revision': row.get('sha256') or row.get('md5') or row.get('modified') or identifier,
                'size': numeric(row.get('size', 0)),
                'url': self.url + '/' + quote(path.lstrip('/'), safe='/')}

    def validate_file(self, file):
        current = self.normalize(self.metadata(file['path']))
        if current['id'] != file['id'] or current['revision'] != file['revision']:
            raise ValueError('Файл изменился во время импорта.')

    def download(self, file):
        if file['kind'] != 'photo':
            raise ValueError('Скачивание видео не предусмотрено.')
        self.validate_file(file)
        data = checked(requests.get(yandex_disk.API + '/public/resources/download', params={
            'public_key': self.url, 'path': self.path(file['path'])}, timeout=(10, 30)))
        url=yandex_disk.provider_href(data.get('href', ''))
        for attempt in range(4):
            response=requests.get(url,stream=True,timeout=(10,60),allow_redirects=False)
            if response.status_code not in {301,302,303,307,308}:return bounded_download(response)
            location=response.headers.get('Location','');response.close()
            if not location:raise ValueError('Диск не вернул адрес фотографии.')
            url=yandex_disk.provider_href(urljoin(url,location))
        raise ValueError('Слишком много перенаправлений при получении фотографии.')
