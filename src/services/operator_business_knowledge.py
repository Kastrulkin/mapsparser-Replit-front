"""Shared knowledge tools for Web chat and Telegram; proposed writes require approval."""
from services import business_knowledge
from services.business_permissions import load_actor


def tools(cursor,business_id,user_id,channel,session=None,message=''):
    if not business_knowledge.installed(cursor):return []
    user=load_actor(cursor,user_id)
    user.update({key:session[key] for key in ('session_kind','scope_business_id') if session and key in session})
    def read(_args):
        data=business_knowledge.read(cursor,'business',business_id,user)
        return {'status':'completed','knowledge':data,'external_writes_performed':False}
    def propose(args):
        from api.business_knowledge_api import prepare_change
        import uuid
        change={**args,'request_id':str(uuid.uuid4())}
        return prepare_change(cursor,'business',business_id,user,change,channel)
    def suggest(args):
        import uuid
        text=str(args.get('text') or '')
        if not text or text.casefold() not in message.casefold():raise ValueError('Предложение должно сохранять слова пользователя.')
        entry=business_knowledge.propose(cursor,business_id,user,text,args.get('record_id'),str(uuid.uuid4()),channel)
        return {'status':'completed','entry_id':entry['id'],'chat_response':'Предложение записано в рабочий журнал для проверки руководством. Постоянные сведения не изменены.','external_writes_performed':False}
    return [
        {'name':'knowledge.read','capability':'settings.read','title':'Знания о бизнесе',
         'description':'Читает сохранённые постоянные характеристики, правила и документы выбранного бизнеса. Нельзя принимать временную доступность из журнала за общую вместимость.',
         'input_schema':{'type':'object','properties':{}},'risk_class':'read_only','approval_required':False,'execute':read},
        {'name':'knowledge.prepare_change','capability':'business.knowledge','title':'Предложить изменение сведений',
         'description':'Готовит сравнение и подтверждение изменения существующего значения или правила по поручению пользователя. Сначала прочитай knowledge.read: нужны id и version. Не сохраняет до подтверждения. Не меняет утверждённые сценарии или внешние системы.',
         'input_schema':{'type':'object','required':['operation','payload'],'properties':{'operation':{'type':'string','enum':['value','rule']},'id':{'type':'string'},'version':{'type':'integer'},'payload':{'type':'object'},'source_entry_id':{'type':'string'}}},
         'risk_class':'internal_write','approval_required':True,'deterministic_preparation_response':True,'prepare_approval':propose},
        {'name':'knowledge.propose_change','capability':'work.journal','title':'Предложение сотрудника',
         'description':'Записывает предложение сотрудника в рабочий журнал с привязкой к полю или правилу. Нужны record_id из knowledge.read и точные слова пользователя. Не меняет постоянные сведения.',
         'input_schema':{'type':'object','required':['record_id','text'],'properties':{'record_id':{'type':'string'},'text':{'type':'string'}}},
         'risk_class':'internal_observation_write','approval_required':False,'deterministic_response':True,'execute':suggest},
    ]
