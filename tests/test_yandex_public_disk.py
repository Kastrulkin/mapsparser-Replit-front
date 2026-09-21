import unittest
from unittest.mock import patch
from services.yandex_public_disk import PublicReader, folder_url

URL='https://disk.360.yandex.ru/d/test_key'
class Response:
    status_code=200
    def __init__(self,data):self.data=data
    def json(self):return self.data

class PublicDiskTests(unittest.TestCase):
    def test_host_path_validation(self):
        self.assertEqual(folder_url(URL+'?utm=test'),URL)
        for value in ['http://disk.yandex.ru/d/key','https://evil.test/d/key','https://disk.yandex.ru@evil.test/d/key','https://disk.yandex.ru/d/../private','https://disk.yandex.ru/d/key/private']:
            with self.assertRaises(ValueError):folder_url(value)
    def test_page_boundaries_and_pagination(self):
        reader=PublicReader(None,{'root_url':URL})
        body={'type':'dir','_embedded':{'offset':0,'total':2,'items':[{'path':'/photo.jpg','name':'photo.jpg','resource_id':'stable','type':'file','mime_type':'image/jpeg','sha256':'revision'}]}}
        with patch('services.yandex_public_disk.requests.get',return_value=Response(body)):
            rows,token=reader.page('/');self.assertEqual(token,1);self.assertEqual(rows[0]['id'],'stable')
            body['_embedded']['items']=[]
            with self.assertRaises(ValueError):reader.page('/')
            body['_embedded']['offset']=5
            with self.assertRaises(ValueError):reader.page('/')
    def test_personal_documents_not_traversed(self):
        reader=PublicReader(None,{'root_url':URL})
        row=reader.normalize({'path':"/Driver's licenses",'name':"Driver's licenses",'resource_id':'private','type':'dir'})
        self.assertEqual(row['kind'],'unsupported')
        mock=patch('services.yandex_public_disk.requests.get');request=mock.start()
        try:
            with self.assertRaises(ValueError):reader.page("/Driver's licenses")
            self.assertFalse(request.called)
        finally:mock.stop()
    def test_video_is_never_downloaded(self):
        reader=PublicReader(None,{'root_url':URL})
        with self.assertRaises(ValueError):reader.download({'kind':'video'})
    def test_changed_file_is_rejected(self):
        reader=PublicReader(None,{'root_url':URL})
        with patch.object(reader,'metadata',return_value={'path':'/x','name':'x','resource_id':'id','sha256':'new'}):
            with self.assertRaises(ValueError):reader.validate_file({'path':'/x','id':'id','revision':'old'})
    def test_path_escape_rejected(self):
        reader=PublicReader(None,{'root_url':URL})
        for path in ['../private','/a/../private','/a/./b']:
            with self.assertRaises(ValueError):reader.path(path)


class RedirectTests(unittest.TestCase):
    def test_foreign_redirect_is_rejected(self):
        reader=PublicReader(None,{'root_url':URL})
        redirect=Response({});redirect.status_code=302;redirect.headers={'Location':'https://evil.test/photo'};redirect.close=lambda:None
        with patch.object(reader,'validate_file'),patch('services.yandex_public_disk.requests.get',side_effect=[Response({'href':'https://downloader.disk.yandex.ru/a'}),redirect]):
            with self.assertRaises(ValueError):reader.download({'kind':'photo','path':'/x'})

class StorageRoutingTests(unittest.TestCase):
    def test_direct_storage_keeps_other_proxy_routes(self):
        from services import media_file_storage
        with patch.dict('os.environ',{'MEDIA_S3_HTTP_PROXY':'direct','OUTBOUND_HTTP_PROXY':'http://unavailable:10809','MEDIA_S3_ACCESS_KEY_ID':'test','MEDIA_S3_SECRET_ACCESS_KEY':'test'}),patch('boto3.client',side_effect=lambda *args,**kwargs:kwargs):
            self.assertEqual(media_file_storage._s3_client()['config'].proxies,{})
            self.assertEqual(media_file_storage._outbound_proxy_url(),'http://unavailable:10809')

if __name__=='__main__':unittest.main()
