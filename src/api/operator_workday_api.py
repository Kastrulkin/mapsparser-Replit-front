"""Workday inputs/settings on the existing Operator API."""
import uuid
from flask import request, jsonify
from core.auth_helpers import require_auth_from_request
from database_manager import DatabaseManager
from services.operator_conversations import _row
from services import operator_workday, operator_attachments


def register_workday_routes(bp):
    def run(handler):
        user=require_auth_from_request()
        if not user:return jsonify({'error':'Требуется авторизация'}),401
        db=DatabaseManager()
        try:
            cursor=db.conn.cursor()
            payload=request.get_json(silent=True) or {}
            business=request.args.get('business_id') or request.form.get('business_id') or payload.get('business_id')
            uid=str(user.get('user_id') or user.get('id') or '')
            actor=operator_workday.authorize(cursor,business,uid)
            value=handler(cursor,business,uid,actor,payload)
            db.conn.commit()
            return jsonify(value)
        except PermissionError:
            db.conn.rollback()
            return jsonify({'error':'Нет доступа к функции или бизнесу'}),403
        except ValueError:
            import sys
            db.conn.rollback()
            return jsonify({'error':str(sys.exception())}),400
        except Exception:
            db.conn.rollback()
            raise
        finally:
            db.close()

    @bp.route('/storage-apps',methods=['GET','POST'])
    def operator_storage_apps():
        from services import storage_oauth_settings
        user=require_auth_from_request()
        if not user:return jsonify({'error':'Требуется авторизация'}),401
        if user.get('session_kind')=='demo':return jsonify({'error':'Настройки недоступны в демо'}),403
        db=DatabaseManager()
        try:
            c=db.conn.cursor();uid=str(user.get('user_id') or user.get('id') or '')
            storage_oauth_settings.authorize(c,uid)
            if request.method=='POST':
                value=storage_oauth_settings.save(c,uid,request.get_json(silent=True) or {})
            else:value=storage_oauth_settings.public_settings(c)
            db.conn.commit()
            response=jsonify(value);response.headers['Cache-Control']='no-store'
            return response
        except PermissionError:
            db.conn.rollback()
            return jsonify({'error':'Настройки доступны только администратору LocalOS.'}),403
        except ValueError:
            import sys
            db.conn.rollback()
            return jsonify({'error':str(sys.exception())}),400
        finally:db.close()

    @bp.route('/disk/status',methods=['GET'])
    def operator_disk_status():
        from services import yandex_disk
        return run(lambda c,b,u,a,p:yandex_disk.status(c,b))

    @bp.route('/disk/connect',methods=['POST'])
    def operator_disk_connect():
        from services import yandex_disk
        return run(lambda c,b,u,a,p:yandex_disk.begin(c,b,u))

    @bp.route('/disk/disconnect',methods=['POST'])
    def operator_disk_disconnect():
        from services import yandex_disk
        return run(lambda c,b,u,a,p:yandex_disk.disconnect(c,b,u))

    @bp.route('/disk/retry',methods=['POST'])
    def operator_disk_retry():
        from services import yandex_disk
        def retry(c,b,u,a,p):
            operator_workday.authorize(c,b,u,owner=True)
            c.execute("UPDATE operator_async_jobs SET status='queued',attempt_count=0,error_text=NULL,next_attempt_at=NOW(),completed_at=NULL WHERE business_id=%s AND kind='yandex_disk_sync' AND status='failed'",(b,))
            return {'queued':yandex_disk.queue_operator_photos(c,b,u)}
        return run(retry)

    @bp.route('/disk/callback',methods=['GET'])
    def operator_disk_callback():
        from services import yandex_disk
        from flask import redirect
        from requests import RequestException
        db=DatabaseManager()
        try:
            c=db.conn.cursor()
            business,user=yandex_disk.finish(c,request.args.get('state',''),request.args.get('code',''))
            yandex_disk.queue_operator_photos(c,business,user)
            db.conn.commit()
            return redirect('/dashboard/operator')
        except (ValueError,PermissionError,RequestException):
            db.conn.rollback()
            return 'Не удалось подключить Диск. Вернитесь в LocalOS и начните подключение заново.',400
        finally:
            db.close()

    @bp.route('/google-drive/status',methods=['GET'])
    def operator_google_drive_status():
        from services import google_drive
        return run(lambda c,b,u,a,p:google_drive.status(c,b))

    @bp.route('/google-drive/connect',methods=['POST'])
    def operator_google_drive_connect():
        from services import google_drive
        return run(lambda c,b,u,a,p:google_drive.begin(c,b,u))

    @bp.route('/google-drive/disconnect',methods=['POST'])
    def operator_google_drive_disconnect():
        from services import google_drive
        return run(lambda c,b,u,a,p:google_drive.disconnect(c,b,u))

    @bp.route('/google-drive/retry',methods=['POST'])
    def operator_google_drive_retry():
        from services import google_drive
        def retry(c,b,u,a,p):
            operator_workday.authorize(c,b,u,owner=True)
            c.execute("UPDATE operator_async_jobs SET status='queued',attempt_count=0,error_text=NULL,next_attempt_at=NOW(),completed_at=NULL WHERE business_id=%s AND kind='google_drive_sync' AND status='failed'",(b,))
            return {'queued':google_drive.queue_operator_photos(c,b,u)}
        return run(retry)

    @bp.route('/google-drive/callback',methods=['GET'])
    def operator_google_drive_callback():
        from services import google_drive
        from flask import redirect
        from requests import RequestException
        db=DatabaseManager()
        try:
            c=db.conn.cursor()
            business,user=google_drive.finish(c,request.args.get('state',''),request.args.get('code',''))
            google_drive.queue_operator_photos(c,business,user)
            db.conn.commit()
            return redirect('/dashboard/operator')
        except (ValueError,PermissionError,RequestException):
            db.conn.rollback()
            return 'Не удалось подключить Диск. Вернитесь в LocalOS и начните подключение заново.',400
        finally:
            db.close()

    @bp.route('/workday/config',methods=['GET'])
    def operator_workday_config():
        def config(cursor,business,user,actor,payload):
            cursor.execute('SELECT recipient_user_id,version FROM operator_pilot_settings WHERE business_id=%s',(business,))
            saved=_row(cursor,cursor.fetchone())
            candidates=[]
            if actor['role']=='owner':
                cursor.execute('''SELECT u.id,u.name FROM users u WHERE u.is_active=TRUE AND NULLIF(u.telegram_id,'') IS NOT NULL
                    AND (u.id=%s OR u.id IN (SELECT owner_id FROM businesses WHERE id=%s)
                    OR u.id IN (SELECT user_id FROM business_members WHERE business_id=%s AND status='active')) ORDER BY u.name''',
                    (user,business,business))
                candidates=[_row(cursor,row) for row in cursor.fetchall()]
            return {'enabled':True,'can_configure':actor['role']=='owner','recipient_user_id':saved.get('recipient_user_id'),
                    'version':saved.get('version',0),'recipients':candidates}
        return run(config)

    @bp.route('/workday/recipient',methods=['POST'])
    def operator_workday_recipient():
        def save(cursor,business,user,actor,payload):
            operator_workday.authorize(cursor,business,user,owner=True)
            recipient=payload.get('recipient_user_id')
            cursor.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('pilot-settings:'+business,))
            cursor.execute('SELECT version FROM operator_pilot_settings WHERE business_id=%s',(business,))
            current=_row(cursor,cursor.fetchone())
            if payload.get('version')!=current.get('version',0):raise ValueError('Настройки изменились. Обновите страницу.')
            if recipient:
                cursor.execute('''SELECT id FROM users WHERE id=%s AND is_active=TRUE AND NULLIF(telegram_id,'') IS NOT NULL
                    AND (id=%s OR id IN (SELECT owner_id FROM businesses WHERE id=%s)
                    OR id IN (SELECT user_id FROM business_members WHERE business_id=%s AND status='active'))''',
                    (recipient,user,business,business))
                if not cursor.fetchone():raise ValueError('Выберите участника с подключённым Telegram.')
            cursor.execute('''INSERT INTO operator_pilot_settings(business_id,recipient_user_id,updated_by) VALUES (%s,%s,%s)
                ON CONFLICT(business_id) DO UPDATE SET recipient_user_id=EXCLUDED.recipient_user_id,
                version=operator_pilot_settings.version+1,updated_by=EXCLUDED.updated_by,updated_at=NOW()''',(business,recipient,user))
            return {'success':True}
        return run(save)

    @bp.route('/attachments',methods=['POST'])
    def operator_attachment_upload():
        request.max_content_length=operator_attachments.MAX_BYTES+65536
        def upload(cursor,business,user,actor,payload):
            file=request.files.get('file')
            if file is None:raise ValueError('Выберите файл.')
            item=operator_attachments.receive(cursor,business_id=business,user_id=user,
                channel=request.form.get('channel','web'),conversation_id=request.form.get('conversation_id') or None,
                content=file.stream.read(operator_attachments.MAX_BYTES+1),name=file.filename or '',mime_type=file.mimetype or '',
                request_key=request.form.get('request_id') or str(uuid.uuid4()))
            # Explicitly selected files are shared with the next voice or text command.
            cursor.execute('SELECT input_context_json FROM operatorconversations WHERE id=%s FOR UPDATE',(item['conversation_id'],))
            context=_row(cursor,cursor.fetchone()).get('input_context_json') or {}
            ids=list(dict.fromkeys((context.get('attachment_ids') or [])+[item['id']]))
            if len(ids)>10:raise ValueError('В одном материале допускается до 10 файлов. Завершите текущий ввод.')
            import json
            context['attachment_ids']=ids
            cursor.execute('UPDATE operatorconversations SET input_context_json=%s::jsonb WHERE id=%s',(json.dumps(context),item['conversation_id']))
            return {'attachment':item,'conversation_id':item['conversation_id']}
        return run(upload)

    @bp.route('/workday/clear-input',methods=['POST'])
    def operator_workday_clear():
        def clear(c,b,u,a,p):
            c.execute("UPDATE operatorconversations SET input_context_json='{}'::jsonb WHERE id=%s AND business_id=%s AND user_id=%s",(p.get('conversation_id'),b,u))
            return {'success':True}
        return run(clear)
