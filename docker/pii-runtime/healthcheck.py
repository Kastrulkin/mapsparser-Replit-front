import http.client
import json
import ssl

try:
    context=ssl.create_default_context(cafile='/run/secrets/pii-ca.crt')
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    connection=http.client.HTTPSConnection('127.0.0.1',8765,context=context,timeout=2)
    connection.request('GET','/health')
    response=connection.getresponse()
    healthy=response.status==200 and json.loads(response.read(1024))=={'status':'ok'}
    connection.close()
except Exception:
    healthy=False
raise SystemExit(0 if healthy else 1)
