import type {
	AgentExecutionMode,
	EmployeeWorkspaceState
} from './types';

export const employeeToneClass = {
  emerald: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  rose: 'bg-rose-50 text-rose-700 ring-rose-200',
  slate: 'bg-slate-100 text-slate-700 ring-slate-200',
};

export const agentExecutionModeOptions: Array<{ value: AgentExecutionMode; label: string; description: string }> = [
  { value: 'one_off', label: 'Сделать один раз', description: 'После выполнения задача попадёт в завершённые.' },
  { value: 'manual', label: 'Запускать по кнопке', description: 'Вы запускаете работу, когда она нужна.' },
  { value: 'scheduled', label: 'По расписанию', description: 'Агент запускается в указанное время.' },
];

export const employeeStateTitle = (state: EmployeeWorkspaceState) => ({
  draft: 'Черновик',
  needs_mode: 'Выберите тип запуска',
  needs_connection: 'Не хватает подключения',
  ready_for_test: 'Готов к проверке',
  running_test: 'Проверка идёт',
  waiting_for_review: 'Ждёт вашего решения',
  waiting_provider: 'Ожидает записи',
  blocked_result: 'Нужен следующий шаг',
  working: 'Работает',
  completed: 'Выполнено',
  needs_attention: 'Нужно включить',
  error: 'Ошибка',
}[state]);
