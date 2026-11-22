"""VPS-only synthetic diagnostics. Reports contain counts/metrics, never secrets."""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import ssl
import statistics
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from services.pii_protection.gateway import PIIProtectionError, Scope
from services.pii_protection.remote import RemoteProtectionService
from services.pii_protection.runtime_config import read_secret_json


def require(condition, code):
    if not condition:
        raise RuntimeError(code)


def percentile(values, p):
    values=sorted(values)
    return round(values[min(len(values)-1, int((len(values)-1)*p/100))],3) if values else None


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['smoke','load','checkpoint','restore','expired','unavailable'])
    parser.add_argument('output')
    parser.add_argument('--seconds',type=int,default=300)
    args=parser.parse_args()
    if not 1<=args.seconds<=600:raise RuntimeError('SYNTHETIC_LOAD_DURATION_INVALID')
    config=read_secret_json('/run/secrets/pii-verify.json')
    client=RemoteProtectionService(**{k:config['client'][k] for k in ['endpoint','bearer_token','ca_pem']})
    scope=Scope('synthetic-business','synthetic-user','synthetic-probe-'+uuid.uuid4().hex)
    result={'mode':args.mode,'business_data_used':False}
    if args.mode=='smoke':
        import redis
        from public_inputs import public_context_for_case
        cases=[json.loads(line) for line in (ROOT/'tests/fixtures/pii/synthetic_200.jsonl').read_text().splitlines()]
        before=client._call('/v1/status',{})
        for case in cases:
            case_scope=Scope(scope.business_id,scope.user_id,'synthetic-case-'+uuid.uuid4().hex)
            exchange=client.protect(case['text'],case_scope,case['policy'],public_context=public_context_for_case(case['id']))
            require(all(e['value'] not in exchange.text for e in case['entities']),'SYNTHETIC_PII_ESCAPE')
            require(all(v in exchange.text for v in case['allowed_public']),'SYNTHETIC_PUBLIC_CONTEXT')
            if not any(e['type']=='SECRET' for e in case['entities']):
                require(exchange.restore_text(exchange.text)==case['text'],'SYNTHETIC_ROUNDTRIP')
        result['scenarios_passed']=len(cases)
        status=client._call('/v1/status',{})
        require(status['model_pid']==before['model_pid'] and status['model_lanes']==1 and status['synthetic_only'],'SYNTHETIC_SINGLE_MODEL')
        result['model_pid']=status['model_pid'];result['tls_version']=client._connection().sock.version()
        bad_auth=RemoteProtectionService(config['client']['endpoint'],'X'*64,config['client']['ca_pem'])
        for peer,expected in [(bad_auth,'PII_RUNTIME_AUTH_REQUIRED')]:
            try:peer.protect('Email: fabricated@example.invalid',scope);raise RuntimeError('SYNTHETIC_AUTH_BYPASS')
            except PIIProtectionError as e:require(str(e)==expected,'SYNTHETIC_AUTH_CODE')
        bad_tls=RemoteProtectionService(config['client']['endpoint'],config['client']['bearer_token'],config['client']['ca_pem'])
        bad_tls._tls=ssl.create_default_context()
        try:bad_tls.protect('Email: fabricated@example.invalid',scope);raise RuntimeError('SYNTHETIC_TLS_BYPASS')
        except PIIProtectionError as e:require(str(e)=='PII_RUNTIME_UNAVAILABLE','SYNTHETIC_TLS_CODE')
        try:client.protect('fabricated',Scope('unapproved-example','fabricated','fabricated'));raise RuntimeError('SYNTHETIC_COHORT_BYPASS')
        except PIIProtectionError as e:require(str(e)=='PII_RUNTIME_COHORT_DENIED','SYNTHETIC_COHORT_CODE')
        verify=redis.Redis.from_url(config['redis_url'],decode_responses=False,socket_timeout=2)
        limited=redis.Redis.from_url(config['runtime_redis_url'],decode_responses=False,socket_timeout=2)
        before_keys=set(verify.scan_iter(match='localos:pii:v1:*',count=100))
        own=client.protect('Email: synthetic-expiry@example.invalid',scope)
        own_keys=set(verify.scan_iter(match='localos:pii:v1:*',count=100))-before_keys
        require(bool(own_keys),'SYNTHETIC_OWN_MAPPING_MISSING')
        token=next(iter(own.issued))
        try:client.resolve(Scope('synthetic-other',scope.user_id,scope.session_id),token);raise RuntimeError('SYNTHETIC_SCOPE_BYPASS')
        except PIIProtectionError as e:require(str(e)=='PII_MAPPING_EXPIRED','SYNTHETIC_SCOPE_CODE')
        denied=[]
        for name,arguments in [('GET',('unrelated:key',)),('SET',('unrelated:key','fabricated')),('CONFIG',('GET','*')),('FLUSHALL',()),('KEYS',('*',))]:
            try:limited.execute_command(name,*arguments);raise RuntimeError('SYNTHETIC_ACL_BYPASS')
            except redis.exceptions.NoPermissionError:denied.append(name)
        keys=list(verify.scan_iter(match='localos:pii:v1:*',count=100))
        require(bool(keys),'SYNTHETIC_NO_MAPPINGS')
        encrypted=0
        for key in keys:
            value=verify.get(key)
            if value is None:continue
            require(value.startswith(b'gAAAA') and b'@example.invalid' not in value and b'"scope"' not in value,'SYNTHETIC_PLAINTEXT_REDIS')
            require(0<verify.ttl(key)<=900,'SYNTHETIC_REDIS_TTL')
            encrypted+=1
        # Mutate only a mapping created in this probe's unique synthetic session.
        candidate=next(iter(own_keys));saved=verify.get(candidate)
        verify.set(candidate,b'synthetic-corrupted',ex=900)
        try:own.restore_text(own.text);raise RuntimeError('SYNTHETIC_CORRUPTION_BYPASS')
        except PIIProtectionError as e:require(str(e)=='PII_MAPPING_INVALID','SYNTHETIC_CORRUPTION_CODE')
        verify.set(candidate,saved,ex=900)
        require(own.restore_text(own.text)=='Email: synthetic-expiry@example.invalid','SYNTHETIC_CORRUPTION_RECOVERY')
        verify.expire(candidate,1)
        time.sleep(1.2)
        try:own.restore_text(own.text);raise RuntimeError('SYNTHETIC_EXPIRY_BYPASS')
        except PIIProtectionError as e:require(str(e)=='PII_MAPPING_EXPIRED','SYNTHETIC_EXPIRY_CODE')
        result.update(acl_denials=denied,ciphertexts_checked=encrypted,ttl_expiry=True,wrong_scope_denied=True,
                      wrong_ca_denied=True,wrong_auth_denied=True,non_synthetic_denied=True)
    elif args.mode=='load':
        phases=[]
        for concurrency,duration in [(1,20),(4,20),(8,20),(4,args.seconds)]:
            latencies=[];errors={};count=0;mutex=threading.Lock();started=time.monotonic();deadline=started+duration
            before=client._call('/v1/status',{})
            def worker(index):
                nonlocal count
                while time.monotonic()<deadline:
                    sample_scope=Scope('synthetic-load','synthetic-user-'+str(index),'synthetic-load-'+uuid.uuid4().hex)
                    began=time.perf_counter();code=None
                    try:
                        exchange=client.protect('Full name: Mira Exampleton; phone: +7 999 000 01 23; email: synthetic-load@example.invalid',sample_scope)
                        require('synthetic-load@example.invalid' not in exchange.text and '+7 999 000 01 23' not in exchange.text,'SYNTHETIC_LOAD_ESCAPE')
                        require(exchange.restore_text(exchange.text)=='Full name: Mira Exampleton; phone: +7 999 000 01 23; email: synthetic-load@example.invalid','SYNTHETIC_LOAD_RESTORE')
                    except PIIProtectionError as e:code=str(e)
                    except Exception:code='SYNTHETIC_LOAD_INTEGRITY_FAILED'
                    with mutex:
                        if code:errors[code]=errors.get(code,0)+1
                        else:count+=1;latencies.append((time.perf_counter()-began)*1000)
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures=[pool.submit(worker,i) for i in range(concurrency)]
                for future in futures:future.result()
            elapsed=time.monotonic()-started;after=client._call('/v1/status',{})
            require(before['model_pid']==after['model_pid'],'SYNTHETIC_MODEL_RESTART_DURING_LOAD')
            require(not(set(errors)-{'PII_RUNTIME_BUSY'}),'SYNTHETIC_UNEXPECTED_LOAD_FAILURE')
            require(count>0,'SYNTHETIC_NO_LOAD_SUCCESSES')
            phases.append({'clients':concurrency,'duration_seconds':round(elapsed,3),'successful_requests':count,
                           'errors':errors,'p50_ms':percentile(latencies,50),'p95_ms':percentile(latencies,95),
                           'p99_ms':percentile(latencies,99),'requests_per_second':round(count/elapsed,3),'model_pid':after['model_pid']})
        result['phases']=phases
    elif args.mode=='checkpoint':
        exchange=client.protect('Email: synthetic-restart@example.invalid',scope)
        result['checkpoint']={'scope':{'business_id':scope.business_id,'user_id':scope.user_id,'session_id':scope.session_id},'token':next(iter(exchange.issued))}
        result['status']=client._call('/v1/status',{})
    elif args.mode in {'restore','expired'}:
        checkpoint=json.loads(Path('/evidence/checkpoint.json').read_text())['checkpoint']
        try:
            value=client.resolve(Scope(**checkpoint['scope']),checkpoint['token'])
            require(args.mode=='restore' and value=='synthetic-restart@example.invalid','SYNTHETIC_RESTART_RESTORE')
            result['mapping_preserved']=True
        except PIIProtectionError as e:
            require(args.mode=='expired' and str(e)=='PII_MAPPING_EXPIRED','SYNTHETIC_RESTART_ERROR')
            result['mapping_expired_fail_closed']=True
    elif args.mode=='unavailable':
        from services.llm import gateway
        from services.llm.contracts import LLMTaskDefinition,LLMTaskRequest
        os.environ['PII_PROTECTION_ENABLED']='true';os.environ['PII_PROTECTION_MODE']='enforce'
        provider_calls=[]
        class FakeAdapter:
            def generate(self,*args,**kwargs):provider_calls.append(1);raise RuntimeError('SYNTHETIC_PROVIDER_MUST_NOT_RUN')
        gateway.get_task_definition=lambda _:LLMTaskDefinition('synthetic-task','deepseek','deepseek_reasoning','business_internal')
        gateway.business_task_definition=lambda definition,_:definition
        gateway._provider_for_request=lambda *_:'deepseek'
        gateway._adapter=lambda _:FakeAdapter()
        gateway._record_result=lambda *_args,**_kwargs:None
        from services.pii_protection import gateway as privacy
        privacy.runtime_service=lambda:client
        response=gateway.run_llm_task(LLMTaskRequest('synthetic-task','Email: synthetic-fault@example.invalid',business_id=scope.business_id,user_id=scope.user_id,pii_session_id=scope.session_id))
        require(response.status=='policy_blocked' and not provider_calls,'SYNTHETIC_FAIL_CLOSED')
        result.update(gateway_status=response.status,reason=response.fallback_reason,provider_calls=0)
    result['outcome']='passed'
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Fixed error types only. Tracebacks can contain configuration objects.
        import re
        reason=str(error)
        print(json.dumps({'status':'failed','error_type':type(error).__name__,
                          'code':reason if re.fullmatch(r'(?:SYNTHETIC|PII)_[A-Z_]+',reason) else None}))
        raise SystemExit(1)
