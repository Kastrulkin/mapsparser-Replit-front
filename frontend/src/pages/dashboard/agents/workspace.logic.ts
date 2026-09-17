
export const humanizeLearningTrigger = (trigger?: string) => ({
  manual_edit: 'Ручная правка',
  approval_rejected: 'Отклонение',
  bad_outcome: 'Плохой результат',
  runtime_error: 'Ошибка',
  manual_feedback: 'Комментарий',
  run_review: 'Проверка запуска',
}[trigger || ''] || trigger || 'Событие обучения');

export const humanizeVersionAction = (action?: string) => ({
  created: 'Создана версия',
  setup_updated: 'Обновлена логика',
  activated: 'Активирована',
  rollback: 'Откат',
  feedback_applied: 'Обратная связь применена',
  legacy_migration_created: 'Создано миграцией',
}[action || ''] || action || 'Событие версии');

export const humanizeVersionState = (state?: string) => ({
  candidate: 'кандидатная версия',
  active: 'активная',
  rolled_back: 'откачена',
  archived: 'в архиве',
}[state || ''] || state || 'кандидатная версия');
