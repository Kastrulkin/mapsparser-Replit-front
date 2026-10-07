"""Google service-list read/compare/append. No provider writes during preview."""
import hashlib
import json
import re
from decimal import Decimal


def version(items):
    return hashlib.sha256(json.dumps(items,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def same_service(expected,actual):
    """Google may omit zero nanos and add default language metadata on read."""
    if expected.get('freeFormServiceItem'):
        left=expected['freeFormServiceItem'];right=actual.get('freeFormServiceItem') or {}
        if left.get('categoryId','').removeprefix('categories/')!=right.get('categoryId','').removeprefix('categories/'):
            return False
        for key in ('displayName','description'):
            if (left.get('label') or {}).get(key,'')!=(right.get('label') or {}).get(key,''):
                return False
    elif expected.get('structuredServiceItem')!=actual.get('structuredServiceItem'):
        return False
    if expected.get('price') is not None:
        left=expected['price'];right=actual.get('price') or {}
        if left.get('currencyCode')!=right.get('currencyCode'):
            return False
        for key in ('units','nanos'):
            if Decimal(str(left.get(key) or 0))!=Decimal(str(right.get(key) or 0)):
                return False
    return expected.get('isOffered',True)==actual.get('isOffered',True)


class GoogleServices:
    def __init__(self, session, location):
        match = re.fullmatch(r'(?:accounts/[^/]+/)?locations/([^/]+)',location or '')
        if not match:
            raise ValueError('В подключении Google не выбрана карточка.')
        self.session = session
        self.location = 'locations/'+match.group(1)
        self.url = 'https://mybusinessbusinessinformation.googleapis.com/v1/'+self.location

    def read(self):
        response = self.session.get(self.url,params={'readMask':'name,title,metadata,categories,serviceItems'},timeout=20)
        response.raise_for_status()
        return response.json()

    def preview(self, service):
        data = self.read()
        if not data.get('metadata',{}).get('canModifyServiceList'):
            raise ValueError('Google не разрешает изменять услуги этой карточки.')
        category = data.get('categories',{}).get('primaryCategory',{}).get('name')
        if not category:
            raise ValueError('Google не вернул категорию карточки.')
        category=category.removeprefix('categories/')
        price = Decimal(str(service['price']))
        units = price // 1
        item = {'freeFormServiceItem':{'categoryId':category,'label':{'displayName':service['name']}},
                'price':{'currencyCode':service['currency'],'units':str(units),'nanos':round((price-units)*1000000000)}}
        if service.get('description'):
            item['freeFormServiceItem']['label']['description']=service['description']
        items = data.get('serviceItems') or []
        for existing in items:
            label=existing.get('freeFormServiceItem',{}).get('label',{}).get('displayName','')
            if label.casefold()==service['name'].casefold():
                raise ValueError('В Google уже есть услуга с таким названием. Нужно отдельно согласовать её изменение.')
        return {'location':self.location,'title':data.get('title'),'version':version(items),'item':item}

    def apply(self, preview):
        if preview.get('location')!=self.location:
            raise ValueError('Карточка Google изменилась. Подготовьте новое подтверждение.')
        data=self.read()
        if not data.get('metadata',{}).get('canModifyServiceList'):
            raise ValueError('Google больше не разрешает запись услуг.')
        items=data.get('serviceItems') or []
        item=preview['item']
        # Reconcile a successful PATCH followed by timeout/crash without resending.
        if any(same_service(item,saved) for saved in items):
            return {'verified':True,'already_present':True}
        if version(items)!=preview['version']:
            raise ValueError('Список услуг Google изменился. Подготовьте новое подтверждение.')
        response=self.session.patch(self.url,params={'updateMask':'serviceItems'},json={'serviceItems':items+[item]},timeout=20)
        response.raise_for_status()
        saved=self.read().get('serviceItems') or []
        if not any(same_service(item,value) for value in saved) or any(not any(same_service(previous,value) for value in saved) for previous in items):
            raise ValueError('Google принял запрос, но проверка сохранённых услуг не завершена. Проверьте статус повторно.')
        return {'verified':True,'already_present':False}


def load_google(cursor,business_id,account_id=None):
    from services.operator_conversations import _row
    cursor.execute("SELECT * FROM externalbusinessaccounts WHERE business_id=%s AND source='google_business' AND (%s IS NULL OR id=%s)",(business_id,account_id,account_id))
    accounts=[_row(cursor,row) for row in cursor.fetchall()]
    if not accounts:
        raise ValueError('Google Business не подключён.')
    if len(accounts)!=1:
        raise ValueError('Подключено несколько карточек Google. Уточните карточку.')
    account=accounts[0]
    from google_business_sync_worker import GoogleBusinessSyncWorker
    api=GoogleBusinessSyncWorker()._get_api_client(account)
    return GoogleServices(api.authed_session,account.get('external_id')),account['id']
