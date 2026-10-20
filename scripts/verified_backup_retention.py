#!/usr/bin/env python3
"""Verified database snapshots only. No recursive archive/data deletion."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import zlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

NAME = re.compile(r'^db-\d{8}T\d{6}Z\.dump$')
MARKER = '.localos-managed-backups-v1'
RESERVE = 3 * 1024**3
CAP = 5 * 1024**3
APP = 'localos-verified-backup-v1'


def sha(path):
    value=hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(4*1024**2),b''):
            value.update(block)
    return value.hexdigest()


def pool(root, create=False):
    current=root
    for component in ('data','backups','verified'):
        current=current/component
        if current.is_symlink(): raise ValueError('Backup directory must not be a symlink')
    if create:
        if current.exists() and any(current.iterdir()) and not (current/MARKER).is_file():
            raise ValueError('Unmanaged nonempty directory; refusing to adopt it')
        current.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(current,0o700)
        marker=current/MARKER
        if marker.is_symlink(): raise ValueError('Symlink ownership marker')
        if not marker.exists(): marker.write_text('LocalOS verified backup store v1\n')
    if current.exists() and not (current/MARKER).is_file():
        raise ValueError('Backup store ownership marker missing')
    return current


def globals_sidecar(plain):
    if plain.is_symlink(): raise ValueError('Symlink globals sidecar')
    if plain.exists():
        if not plain.is_file() or not plain.stat().st_size: raise ValueError('Missing globals sidecar')
        return plain
    compressed=plain.with_name(plain.name+'.gz')
    if compressed.is_symlink() or not compressed.is_file(): raise ValueError('Missing globals sidecar')
    size=0
    try:
        with gzip.open(compressed,'rb') as source:
            for block in iter(lambda:source.read(1024**2),b''): size+=len(block)
    except (OSError,EOFError,zlib.error) as error:
        raise ValueError('Invalid compressed globals sidecar') from error
    if not size: raise ValueError('Empty compressed globals sidecar')
    return compressed


def records(folder, now):
    valid=[]; warnings=[]
    if not folder.exists(): return valid,warnings
    for manifest in folder.glob('db-*.verified.json'):
        try:
            if manifest.is_symlink(): raise ValueError('symlink manifest')
            record=json.loads(manifest.read_text())
            name=record['name']
            if not NAME.fullmatch(name) or manifest.name!=name+'.verified.json': raise ValueError('bad name')
            path=folder/name
            created=datetime.fromisoformat(record['created_at'])
            if created.tzinfo is None or created>now+timedelta(minutes=5): raise ValueError('bad date')
            if record.get('version')!=1 or record.get('full_archive_read') is not True: raise ValueError('unverified')
            if path.is_symlink() or not path.is_file(): raise ValueError('not a regular dump')
            stat=path.stat()
            if stat.st_size!=record['size'] or sha(path)!=record['sha256']: raise ValueError('checksum mismatch')
            globals_sidecar(folder/(name+'.globals.sql'))
            for suffix in ('.toc',):
                side=folder/(name+suffix)
                if side.is_symlink() or not side.is_file() or not side.stat().st_size: raise ValueError('missing sidecar')
            record={**record,'created':created,'identity':(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns),
                    'pinned':(folder/'.keep').exists() or (folder/(name+'.keep')).exists()}
            valid.append(record)
        except (ValueError,KeyError,TypeError,OSError) as error:
            warnings.append(manifest.name+': '+str(error))
    return sorted(valid,key=lambda r:r['created'],reverse=True),warnings


def removal_plan(items, now, cap=CAP):
    keep={r['name'] for r in items[:2]} | {r['name'] for r in items if r['pinned']}
    older=[r for r in items[2:] if r['created'].date()<now.date()-timedelta(days=6) and r['created']>now-timedelta(days=28)]
    if older: keep.add(older[0]['name'])
    total=sum(r['size'] for r in items if r['name'] in keep)
    for record in reversed(older[:1]):
        if total>cap and record['name'] not in {r['name'] for r in items[:2]} and not record['pinned']:
            keep.discard(record['name']);total-=record['size']
    return [r for r in items if r['name'] not in keep]


def command(root,args,**kwargs):
    return subprocess.run(['docker','compose','exec','-T','postgres',*args],cwd=root,check=True,timeout=900,**kwargs)


def atomic_json(path,value):
    temp=path.with_name(path.name+'.tmp')
    if temp.exists() or temp.is_symlink(): raise ValueError('Stale metadata temporary file')
    with temp.open('x',encoding='utf8') as target:
        os.chmod(temp,0o600)
        json.dump(value,target,default=str,indent=2);target.write('\n');target.flush();os.fsync(target.fileno())
    temp.replace(path)


def validate_archive(root,path,toc):
    with path.open('rb') as source,toc.open('xb') as target:
        command(root,['pg_restore','--list'],stdin=source,stdout=target)
    with path.open('rb') as source:
        command(root,['pg_restore','--file=/dev/null'],stdin=source,stdout=subprocess.DEVNULL)


def commit_record(folder,path,created,extra=None):
    for item in (path,globals_sidecar(folder/(path.name+'.globals.sql')),folder/(path.name+'.toc')):
        with item.open('rb') as handle: os.fsync(handle.fileno())
    record={'version':1,'name':path.name,'created_at':created.isoformat(),'size':path.stat().st_size,
            'sha256':sha(path),'full_archive_read':True,**(extra or {})}
    atomic_json(folder/(path.name+'.verified.json'),record)
    return record


def adopt(root,folder):
    # Explicit, already verified recovery point from the user-approved cleanup.
    original=root/'backups/retention-20261019/local-20261019.dump'
    if original.is_symlink() or not original.is_file(): raise ValueError('Seed recovery point missing')
    expected=(original.parent/'fresh.sha256').read_text().split()[0]
    if sha(original)!=expected: raise ValueError('Seed checksum mismatch')
    created=datetime.fromtimestamp(original.stat().st_mtime,timezone.utc)
    name='db-'+created.strftime('%Y%m%dT%H%M%SZ')+'.dump';dest=folder/name
    if dest.exists(): raise ValueError('Seed already present; use normal --apply')
    # Immutable dated dumps are never overwritten; this saves a second 1.5 GB.
    os.link(original,dest)
    try:
        validate_archive(root,dest,folder/(name+'.toc'))
        source=globals_sidecar(original.parent/'globals.sql')
        side=folder/(name+'.globals.sql'+('.gz' if source.suffix=='.gz' else ''))
        shutil.copyfile(source,side)
        os.chmod(side,0o600)
        return commit_record(folder,dest,created,{'seed_source':str(original)})
    except Exception:
        for suffix in ('','.toc','.globals.sql','.globals.sql.gz'):
            (folder/(name+suffix)).unlink(missing_ok=True)
        raise


def create_backup(root,folder,now,previous):
    estimate=max(1024**3,int((previous[0]['size'] if previous else 2*1024**3)*1.3))
    if shutil.disk_usage(root).free<RESERVE+estimate:
        raise RuntimeError('Not enough headroom: old verified backups retained, no new dump started')
    name='db-'+now.strftime('%Y%m%dT%H%M%SZ')+'.dump';partial=folder/(name+'.partial');final=folder/name
    if final.exists() or partial.exists(): raise ValueError('Snapshot name already exists')
    for suffix in ('.toc','.globals.sql','.verified.json','.stderr.log'):
        side=folder/(name+suffix)
        if side.exists() or side.is_symlink(): raise ValueError('Snapshot sidecar name already exists')
    process=None;committed=False;published=False
    try:
        with partial.open('xb') as target,(folder/(name+'.stderr.log')).open('xb') as error:
            process=subprocess.Popen(['docker','compose','exec','-T','-e','PGAPPNAME='+APP,'postgres','sh','-c',
                'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --compress=zstd:level=6 --lock-wait-timeout=10000'],cwd=root,stdout=target,stderr=error)
            start=time.monotonic()
            while process.poll() is None:
                if shutil.disk_usage(root).free<RESERVE or time.monotonic()-start>1800:
                    raise RuntimeError('Backup stopped at reserve/time limit; old snapshots retained')
                time.sleep(3)
            if process.returncode: raise RuntimeError('pg_dump failed; old snapshots retained')
            target.flush();os.fsync(target.fileno())
        validate_archive(root,partial,folder/(name+'.toc'))
        with (folder/(name+'.globals.sql')).open('xb') as target:
            command(root,['sh','-c','pg_dumpall -U "$POSTGRES_USER" --globals-only --no-role-passwords'],stdout=target)
        os.link(partial,final);published=True;partial.unlink()
        record=commit_record(folder,final,now);committed=True
        return record
    finally:
        if process and process.poll() is None:
            try:
                command(root,['sh','-c','psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "SELECT pg_cancel_backend(pid) FROM pg_stat_activity WHERE application_name=\''+APP+'\' AND pid<>pg_backend_pid();"'],stdout=subprocess.DEVNULL)
            finally:
                try: process.wait(timeout=30)
                except subprocess.TimeoutExpired: process.kill();process.wait()
        if not committed:
            owned=[partial,folder/(name+'.toc'),folder/(name+'.globals.sql')]
            if published: owned.append(final)
            for path in owned:
                path.unlink(missing_ok=True)


def rotate(folder,items,now):
    removed=[]
    for record in removal_plan(items,now):
        if (folder/'.keep').exists(): break
        path=folder/record['name'];stat=path.lstat()
        if path.is_symlink() or (stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns)!=record['identity']:
            raise ValueError('Snapshot changed since verification; nothing more will be deleted')
        if (folder/(record['name']+'.keep')).exists(): continue
        for suffix in ('.verified.json','.globals.sql','.globals.sql.gz','.toc','.stderr.log'):
            if (folder/(record['name']+suffix)).is_symlink(): raise ValueError('Sidecar symlink rejected')
        path.unlink()
        for suffix in ('.verified.json','.globals.sql','.globals.sql.gz','.toc','.stderr.log'):
            side=folder/(record['name']+suffix)
            if side.is_symlink(): raise ValueError('Sidecar symlink rejected')
            side.unlink(missing_ok=True)
        removed.append(record['name'])
    return removed


def run(root,apply=False,seed=False,now=None):
    now=now or datetime.now(timezone.utc);folder=pool(root,create=apply)
    if not apply:
        items,warnings=records(folder,now)
        return {'mode':'preview','verified':len(items),'would_remove':[r['name'] for r in removal_plan(items,now)],'warnings':warnings,'reserve_bytes':RESERVE,'managed_cap_bytes':CAP}
    if (folder/'.lock').is_symlink(): raise ValueError('Symlink backup lock')
    with (folder/'.lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: return {'status':'already_running'}
        os.umask(0o077)
        items,warnings=records(folder,now)
        if seed:
            adopt(root,folder);items,warnings=records(folder,now)
        today=now.astimezone(ZoneInfo('Europe/Moscow')).date()
        created=False
        if not items or items[0]['created'].astimezone(ZoneInfo('Europe/Moscow')).date()!=today:
            create_backup(root,folder,now,items);created=True
            items,warnings=records(folder,now)
        if not items: raise RuntimeError('No verified snapshot; rotation blocked')
        removed=rotate(folder,items,now)
        latest=items[0]
        pointer=folder/'latest.dump';temp=folder/'latest.dump.tmp'
        if pointer.exists() and not pointer.is_symlink(): raise ValueError('Foreign latest.dump file')
        if temp.exists() or temp.is_symlink(): raise ValueError('Stale latest pointer')
        temp.symlink_to(latest['name']);temp.replace(pointer)
        result={'status':'verified','created_new_dump':created,'latest':latest['name'],'sha256':latest['sha256'],
                'removed':removed,'verified_retained':len(items)-len(removed),'warnings':warnings,
                'free_bytes':shutil.disk_usage(root).free,'reserve_bytes':RESERVE,'managed_cap_bytes':CAP}
        retained_bytes=sum(r['size'] for r in items if r['name'] not in removed)
        result['retained_bytes']=retained_bytes
        if retained_bytes>CAP: result['warnings'].append('Minimum recovery points or pins exceed target cap; preserved')
        atomic_json(folder/'last-success.json',result)
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--adopt-existing',action='store_true')
    args=parser.parse_args()
    if args.adopt_existing and not args.apply: parser.error('Adoption requires --apply')
    print(json.dumps(run(Path(__file__).resolve().parents[1],apply=args.apply,seed=args.adopt_existing),indent=2))
