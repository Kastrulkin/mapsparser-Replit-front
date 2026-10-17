"""Reusable child-education editorial guidance, not facts about any school."""
import re


EDUCATION_REFERENCE_QUERY = (
    r'робототех|подготовк.{0,30}школ|программирован.{0,35}дет|'
    r'дет.{0,35}программирован|школ|ученик|школьник|дошкольник|'
    r'\mScratch\M|\mRoblox\M|\mLogiscool\M|\mAlgorithmics\M|'
    r'\mcoding\M|\mchildren\M|\mpreschool\M'
)


def is_education_editorial_reference(text):
    value = str(text or '').casefold()
    if re.search(r'беремен|родов|грудн.{0,15}вскарм|автошкол|школ.{0,12}вожден|#стартап|венчур|инвестор|открыть.{0,30}(школ|бизнес)|франшиз|\bfranchise\b', value):
        return False
    return bool(re.search(r'робототех|дошколь|школьник|ученик|подготовк.{0,25}школ|реб[её]нок|дет[ьи]|\bscratch\b|\broblox\b|\blogiscool\b|\bcoding\b|\bchildren\b|\bpreschool\b', value))


def education_editorial_guidance():
    """Human-reviewed source-derived techniques, with no engagement claims."""
    return [
        {'id': 'education_guidance_project_v1', 'source_type': 'editorial_guidance',
         'techniques': ['показать конкретную задачу или проект вместо перечня курсов',
                        'назвать результат только если он подтверждён программой этого бизнеса'],
         'strength': 'редакционный ориентир, не доказательство эффективности или фактов школы',
         'source_url': 'https://algorithmicschool.com/news/what-kids-learn-coding-courses-portfolio'},
        {'id': 'education_guidance_process_v1', 'source_type': 'editorial_guidance',
         'techniques': ['объяснять навык через последовательность действий: придумать, попробовать, проверить',
                        'не обещать сроки освоения, успешность или будущую профессию'],
         'strength': 'редакционный ориентир, не чужая программа для копирования',
         'source_url': 'https://www.logiscool.com/en/curriculum'},
        {'id': 'education_guidance_interest_v1', 'source_type': 'editorial_guidance',
         'techniques': ['начинать с интереса ребёнка: персонаж, история, конструкция или вопрос',
                        'отделять пример возможного задания от реальной работы ученика'],
         'strength': 'редакционный ориентир творческого обучения, не отзыв об этой школе',
         'source_url': 'https://scratchfoundation.org/learn/learning-library'},
    ]
