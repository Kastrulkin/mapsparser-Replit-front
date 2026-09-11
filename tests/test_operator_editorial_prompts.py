import pytest
from tests.test_operator_news_generation import FakeCursor
from services.operator_news_generation import generate_news_draft_from_operator
from services.operator_social_post_generation import generate_social_post_draft_from_operator


class EditorialCursor(FakeCursor):
    def fetchone(self):
        if 'information_schema.columns' in self.last_query:
            return {'columns':list(self.last_params[1])}
        if 'content_voice_profiles' in self.last_query:
            return {'preferences_json': {'tone_instruction':'Спокойно, от первого лица', 'editorial_notes':[
                {'id':'note','kind':'company_fact','text':'Работаем 25 лет','source':'user_statement'}]}}
        return super().fetchone()


@pytest.mark.parametrize('kind',['news','social'])
def test_standalone_generation_receives_persistent_facts_and_tone(kind):
    cursor=EditorialCursor(balance=100)
    prompts=[]
    def generate(prompt,**kwargs):
        prompts.append(prompt)
        return '{"news":"Мы работаем 25 лет."}' if kind=='news' else '{"post":"Мы работаем 25 лет."}'
    if kind=='news':
        result=generate_news_draft_from_operator(cursor,business_id='biz-1',user_id='user-1',message='Подготовь новость: расскажем про историю компании',news_generator=generate)
    else:
        result=generate_social_post_draft_from_operator(cursor,business_id='biz-1',user_id='user-1',message='Подготовь пост для соцсетей: история компании',post_generator=generate)
    assert result['status']=='completed'
    assert 'Работаем 25 лет' in prompts[0]
    assert 'Спокойно, от первого лица' in prompts[0]
