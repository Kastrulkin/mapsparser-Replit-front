import ast
from pathlib import Path

def test_saved_post_uses_confirmed_photo_and_total_charge_once():
    module=ast.parse(Path('src/services/telegram_dashboard.py').read_text())
    node=next(node for node in module.body if isinstance(node,ast.FunctionDef) and node.name=='_format_operator_chat_result_for_telegram')
    scope={'Any':object,'_base_web_url':lambda:'https://localos.pro'}
    exec(compile(ast.Module(body=[node],type_ignores=[]),'draft_renderer','exec'),scope)
    result=scope[node.name]({'status':'completed','intent':'operator_tool_loop','chat_response':'Фото photo_asset_ids и неверно списан 1 кредит',
        'social_post_text':'Три точных шага для владельца.', 'social_post_draft':{'id':'d','generated_text':'Три точных шага для владельца.'},
        'photo_asset_ids':['p1'],'charged_credits':2,'manual_publication_only':True})
    assert result.count('Три точных шага для владельца.')==1
    assert 'Фотографий: 1.' in result
    assert 'Всего списано кредитов: 2.' in result
    assert 'photo_asset_ids' not in result


def test_brief_without_saved_id_uses_brief_label_in_both_messengers():
    import telegram_bot
    for platform in ('telegram','max'):
        result={'status':'completed','capability':'work.day_brief','chat_response':'Планёрка дня',
            'work_return_url':f'https://localos.pro/{platform}/control?screen=work_journal&scope_id=b1'}
        markup=telegram_bot._build_operator_result_markup(result)
        assert markup.inline_keyboard[0][0].text=='Открыть планёрку'
        assert markup.inline_keyboard[0][0].web_app.url==result['work_return_url']
        module=ast.parse(Path('src/services/telegram_dashboard.py').read_text())
        node=next(n for n in module.body if isinstance(n,ast.FunctionDef) and n.name=='_format_operator_chat_result_for_telegram')
        scope={'Any':object,'_base_web_url':lambda:'https://localos.pro'}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'brief_renderer','exec'),scope)
        text=scope[node.name](result)
        assert 'Открыть чат с LocalOS:' not in text
        assert 'Планёрка дня' in text
