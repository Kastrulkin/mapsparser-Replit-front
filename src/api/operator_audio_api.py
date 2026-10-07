"""Registered on the existing authenticated Operator blueprint."""
import uuid
from flask import jsonify, request, send_file
from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.operator_audio import (MAX_BYTES, authorize_actor, create_transcription, create_speech,
    load_asset, private_path, enabled)


def register_audio_routes(bp):
    def run(handler):
        user = require_auth_from_request()
        if not user:
            return jsonify({'error':'Требуется авторизация'}),401
        db = DatabaseManager()
        try:
            cursor = db.conn.cursor()
            business_id = request.args.get('business_id')
            if request.endpoint.endswith('operator_audio_transcribe'):
                request.max_content_length = MAX_BYTES + 65536
                business_id = request.form.get('business_id')
            asset_id = (request.view_args or {}).get('asset_id')
            message_id = (request.view_args or {}).get('message_id')
            if asset_id or message_id:
                table = 'operator_audio_assets' if asset_id else 'operatormessages'
                cursor.execute('SELECT business_id FROM '+table+' WHERE id=%s AND user_id=%s',(asset_id or message_id,str(user.get('user_id') or user.get('id'))))
                from services.operator_conversations import _row
                business_id = _row(cursor,cursor.fetchone()).get('business_id')
            if not business_id or not verify_business_access(cursor,business_id,user)[0]:
                raise PermissionError('Нет доступа к бизнесу')
            result = handler(cursor,str(user.get('user_id') or user.get('id')))
            db.conn.commit()
            return result
        except PermissionError:
            db.conn.rollback()
            return jsonify({'error':'Нет доступа к записи, бизнесу или Оператору'}),403
        except ValueError:
            import sys
            db.conn.rollback()
            return jsonify({'error':str(sys.exception())}),400
        finally:
            db.close()

    @bp.route('/audio/config',methods=['GET'])
    def operator_audio_config():
        def handler(cursor,user_id):
            business_id=request.args.get('business_id','')
            authorize_actor(cursor,user_id,business_id)
            return jsonify({'input_enabled':enabled('transcription',business_id),'output_enabled':enabled('speech',business_id)})
        return run(handler)

    @bp.route('/audio/transcriptions',methods=['POST'])
    def operator_audio_transcribe():
        def handler(cursor,user_id):
            request.max_content_length = MAX_BYTES + 65536
            business_id=request.form.get('business_id','')
            authorize_actor(cursor,user_id,business_id)
            if request.content_length and request.content_length>MAX_BYTES+65536:
                return jsonify({'error':'Максимальный размер записи — 10 МБ'}),413
            file=request.files.get('file')
            if not file:
                raise ValueError('Добавьте аудиозапись')
            result=create_transcription(cursor,content=file.stream.read(MAX_BYTES+1),user_id=user_id,business_id=business_id,
                channel=request.form.get('channel','web'),conversation_id=request.form.get('conversation_id') or None,
                request_id=request.form.get('request_id') or str(uuid.uuid4()))
            return jsonify(result),202
        return run(handler)

    @bp.route('/messages/<message_id>/speech',methods=['POST'])
    def operator_audio_speech(message_id):
        return run(lambda cursor,user_id:(jsonify(create_speech(cursor,user_id=user_id,message_id=message_id)),202))

    @bp.route('/audio/<asset_id>',methods=['GET'])
    def operator_audio_download(asset_id):
        def handler(cursor,user_id):
            asset=load_asset(cursor,asset_id,user_id)
            if asset['kind']!='speech' or asset['status']!='ready' or not asset.get('path'):
                raise ValueError('Аудио пока не готово')
            response=send_file(private_path(asset['path']),mimetype=asset.get('format') or 'audio/ogg',conditional=False)
            response.headers['Cache-Control']='private, no-store'
            return response
        return run(handler)

    @bp.route('/audio/<asset_id>/cancel',methods=['POST'])
    def operator_audio_cancel(asset_id):
        def handler(cursor,user_id):
            asset=load_asset(cursor,asset_id,user_id)
            if asset['status']=='submitted':
                raise ValueError('Команда уже передана Оператору')
            cursor.execute("UPDATE operator_async_jobs SET status='cancelled',lease_token=NULL WHERE id=%s AND status IN ('queued','running','waiting_for_review')",(asset.get('job_id'),))
            cursor.execute("UPDATE operator_audio_assets SET status='cancelled' WHERE id=%s",(asset_id,))
            return jsonify({'success':True})
        return run(handler)
