"""MAX command discovery; business commands retain their own access checks."""
MAX_COMMANDS = (
    ('start', 'Главное меню'), ('control', 'Открыть LocalOS'), ('businesses', 'Бизнесы и сети'),
    ('use_business', 'Выбрать бизнес'), ('help', 'Справка'), ('cancel', 'Отменить текущий шаг'),
    ('status', 'Статус автоматизации'), ('reply_review', 'Подготовить ответ на отзыв'),
    ('optimize_service', 'Улучшить описание услуги'), ('services_audit', 'Проверить услуги'),
    ('generate_news', 'Подготовить новость'), ('partnerships', 'Партнёрства'),
    ('feature_request', 'Запросить автоматизацию'), ('actions', 'Последние действия'),
    ('action_status', 'Проверить действие по ID'), ('pending_approvals', 'Ожидают решения'),
    ('approve_action', 'Подтвердить действие по ID'), ('reject_action', 'Отклонить действие по ID'),
    ('support_export', 'Подготовить отчёт поддержки'), ('recovery_report', 'Просмотреть восстановление очереди'),
    ('industry_patterns', 'Правила отрасли: администратор'),
    ('industry_patterns_impact', 'Эффект правил: администратор'),
    ('industry_patterns_recalibrate', 'Обновить правила: администратор'),
)


def max_command_menu():
    return [{'name': name, 'description': description} for name, description in MAX_COMMANDS]
