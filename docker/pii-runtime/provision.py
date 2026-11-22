"""Generate VPS-local secrets. Output contains only paths and public TLS metadata."""

import base64
import datetime
import hashlib
import ipaddress
import json
import os
import secrets
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


ROOT = Path('/secrets')
existing = {path.name for path in ROOT.iterdir()}
if existing and existing != {'ca.key', 'ca.crt', 'server.key'}:
    raise SystemExit('PII_SECRET_DIRECTORY_NOT_EMPTY')
for name in existing:
    path = ROOT/name
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise SystemExit('PII_EXISTING_SECRET_UNSAFE')


def write(name, data, owner, mode=0o400):
    target = ROOT/name
    encoded = data.encode() if isinstance(data, str) else data
    if target.exists():
        if name not in {'ca.key', 'ca.crt', 'server.key'} or target.read_bytes() != encoded:
            raise SystemExit('PII_EXISTING_SECRET_MISMATCH')
        os.chmod(target, mode)
        os.chown(target, owner, owner)
        return
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        os.write(descriptor, encoded)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.chmod(target, mode)
    os.chown(target, owner, owner)


now = datetime.datetime.now(datetime.timezone.utc)
ca_key = (serialization.load_pem_private_key((ROOT/'ca.key').read_bytes(), password=None)
          if existing else rsa.generate_private_key(public_exponent=65537, key_size=2048))
ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'LocalOS private PII CA')])
if existing:
    ca = x509.load_pem_x509_certificate((ROOT/'ca.crt').read_bytes())
    if ca.public_key().public_numbers() != ca_key.public_key().public_numbers():
        raise SystemExit('PII_EXISTING_CA_KEY_MISMATCH')
else:
    ca = (x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name).public_key(ca_key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
          .not_valid_after(now+datetime.timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(ca_key, hashes.SHA256()))
server_key = (serialization.load_pem_private_key((ROOT/'server.key').read_bytes(), password=None)
              if existing else rsa.generate_private_key(public_exponent=65537, key_size=2048))
server_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localos-pii-runtime')])
cert = (x509.CertificateBuilder().subject_name(server_name).issuer_name(ca_name).public_key(server_key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
        .not_valid_after(now+datetime.timedelta(days=90))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectAlternativeName([x509.DNSName('localos-pii-runtime'),x509.DNSName('localhost'),
                                                   x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
        .sign(ca_key, hashes.SHA256()))
ca_pem=ca.public_bytes(serialization.Encoding.PEM).decode()
private=lambda key:key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
write('ca.key',private(ca_key),0)
write('ca.crt',ca_pem,0,0o444)
write('server.key',private(server_key),10001)
write('server.crt',cert.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM),10001,0o444)
api_token=secrets.token_urlsafe(48)
mapping_key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
passwords={name:secrets.token_urlsafe(48) for name in ['pii_runtime','pii_verify','pii_health']}
redis_url=lambda name:'redis://'+name+':'+passwords[name]+'@localos-pii-redis:6379/0'
client={'version':1,'endpoint':'https://localos-pii-runtime:8765','bearer_token':api_token,'ca_pem':ca_pem}
server={'version':1,'bearer_token':api_token,'mapping_key':mapping_key,'redis_url':redis_url('pii_runtime'),
        'mapping_ttl_seconds':900,'recognition_timeout_seconds':10,'synthetic_only':True,
        'protect_rps':10,'protect_burst':4,'business_protect_rps':4,'business_protect_burst':4}
verify={'version':1,'client':client,'redis_url':redis_url('pii_verify'),'runtime_redis_url':redis_url('pii_runtime')}
write('client.json',json.dumps(client),0,0o600)
write('runtime.json',json.dumps(server),10001)
write('verify.json',json.dumps(verify),10001)
write('redis-health.password',passwords['pii_health'],999)
acl=['user default off']
for name,commands in [('pii_runtime','+ping +get +set +select +client|setinfo'),
                      ('pii_verify','+ping +get +set +scan +ttl +expire +info +select +client|setinfo'),
                      ('pii_health','+ping +client|setinfo')]:
    acl.append('user '+name+' on #'+hashlib.sha256(passwords[name].encode()).hexdigest()+' ~localos:pii:v1:* '+commands)
write('users.acl','\n'.join(acl)+'\n',999)
write('redis.conf','''bind 0.0.0.0
protected-mode yes
port 6379
databases 1
aclfile /run/secrets/users.acl
save ""
appendonly no
maxmemory 64mb
maxmemory-policy noeviction
maxclients 64
timeout 60
tcp-keepalive 60
loglevel warning
slowlog-log-slower-than -1
latency-monitor-threshold 0
client-output-buffer-limit normal 1mb 256kb 5
dir /data
''',999)
print(json.dumps({'secrets_created':True,'existing_tls_key_material_preserved':bool(existing),'secret_values_emitted':False,'synthetic_only':True,
                  'certificate_expires':cert.not_valid_after_utc.isoformat(),
                  'ca_sha256':ca.fingerprint(hashes.SHA256()).hex()}))
