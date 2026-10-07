"""Inbound sources on the existing media API; platform credentials remain admin-only."""
import sys
from flask import jsonify,request
from core.auth_helpers import require_auth_from_request,session_allows_business
from database_manager import DatabaseManager
from services import disk_import,disk_import_providers,disk_import_media,storage_oauth_settings


def register_disk_import_routes(bp):
    def run(handler,admin=False):
        user=require_auth_from_request()
        if not user:return jsonify({'error':'Требуется авторизация'}),401
        if user.get('session_kind')=='demo':return jsonify({'error':'Импорт недоступен в демо-сессии'}),403
        db=DatabaseManager()
        try:
            c=db.conn.cursor();uid=user.get('user_id') or user.get('id');payload=request.get_json(silent=True) or {}
            if not isinstance(payload,dict):raise ValueError('Ожидается объект настроек.')
            business=request.args.get('business_id') or payload.get('business_id')
            if admin:storage_oauth_settings.authorize(c,uid)
            else:
                if not session_allows_business(user,business):raise PermissionError()
                disk_import.authorize(c,business,uid)
            result=handler(c,business,uid,payload);db.conn.commit()
            response=jsonify(result);response.headers['Cache-Control']='no-store';return response
        except PermissionError:
            db.conn.rollback();return jsonify({'error':'Нет доступа к этой функции или бизнесу.'}),403
        except ValueError:
            error=str(sys.exception());db.conn.rollback();return jsonify({'error':error}),400
        except Exception:
            db.conn.rollback();return jsonify({'error':'Не удалось выполнить действие. Повторите позже.'}),503
        finally:db.close()

    @bp.route('/disk-import/google-reader',methods=['GET','POST'])
    def google_reader_settings():
        request.max_content_length=16384
        return run(lambda c,b,u,p:disk_import_providers.save_google_settings(c,u,p) if request.method=='POST' else disk_import_providers.google_settings(c),admin=True)

    @bp.route('/disk-import',methods=['GET'])
    def source_status():return run(lambda c,b,u,p:disk_import.status(c,b,u))

    @bp.route('/disk-import/prepare',methods=['POST'])
    def source_prepare():return run(disk_import.prepare)

    @bp.route('/disk-import/verify',methods=['POST'])
    def source_verify():return run(disk_import.verify)

    @bp.route('/disk-import/action',methods=['POST'])
    def source_action():return run(disk_import.action)

    @bp.route('/disk-import/videos',methods=['GET'])
    def videos_list():return run(lambda c,b,u,p:disk_import_media.listing(c,b,u,request.args.get('item_id')))

    @bp.route('/disk-import/videos/select',methods=['POST'])
    def videos_select():return run(disk_import_media.attach)
