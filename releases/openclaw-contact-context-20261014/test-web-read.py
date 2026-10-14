"""Offline bridge regression; gateway and network entrypoints are stubbed."""
import importlib.util
import sys
spec=importlib.util.spec_from_file_location('web_read_under_test',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.public_url=lambda url:url
calls=[]
def read(method,path,headers,payload):
    calls.append(payload['url'])
    return 200, {'source':{'text':'Public business email: sales@example.org\nPhuket tours from India',
        'final_url':'https://example.org/package/','fetched_at':'2026-10-14T00:00:00Z'}}
m.handle_web_read=read
r=m.research_website({'url':'https://example.org/package','business_id':'b','job_id':'j',
                     'requirements':['sells Phuket tours'],
                     'known_source_urls':['https://example.org/package/']},{})
assert len(calls)==1, calls
assert len(r['pages'])==1
assert r['contacts'][0]['value']=='sales@example.org'
assert r['contacts'][0]['source_url']=='https://example.org/package/'
assert r['paid_fallback'] is False
print('canonical-page/contact bridge fixtures passed; no network used')
