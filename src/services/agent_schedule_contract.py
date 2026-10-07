"""Shared schedule normalization for Operator and the existing automation editor."""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ScheduleError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def apply_schedule(version, changes, *, business_timezone=None):
    previous = version.get('schedule') or {}
    schedule = dict(previous)
    for key in ('time', 'timezone', 'weekday'):
        if key in changes:
            schedule[key] = changes[key]
    schedule_time = schedule.get('time', '09:00')
    try:
        schedule['time'] = datetime.strptime(str(schedule_time), '%H:%M').strftime('%H:%M')
    except ValueError:
        raise ScheduleError('SCHEDULE_TIME_INVALID', 'Укажите время в формате ЧЧ:ММ.')
    zone_name = schedule.get('timezone') or business_timezone
    if not zone_name:
        raise ScheduleError('SCHEDULE_TIMEZONE_REQUIRED', 'Укажите часовой пояс бизнеса.')
    try:
        ZoneInfo(str(zone_name))
    except (ValueError, ZoneInfoNotFoundError):
        raise ScheduleError('SCHEDULE_TIMEZONE_INVALID', 'Укажите корректный часовой пояс.')
    schedule['timezone'] = str(zone_name)
    trigger = changes.get('trigger') or version.get('trigger') or 'schedule.daily'
    if trigger == 'manual.run':
        trigger = 'schedule.daily'
    if trigger not in {'schedule.daily', 'schedule.weekly'}:
        raise ScheduleError('SCHEDULE_TRIGGER_INVALID', 'Выберите ежедневный или еженедельный запуск.')
    if trigger == 'schedule.weekly':
        weekday = schedule.get('weekday')
        if not isinstance(weekday, int) or isinstance(weekday, bool) or not 0 <= weekday <= 6:
            raise ScheduleError('SCHEDULE_WEEKDAY_INVALID', 'Выберите день недели.')
    else:
        schedule.pop('weekday', None)
    return {**version, 'execution_mode': 'scheduled', 'trigger': trigger, 'schedule': schedule}


def describe_schedule(trigger, schedule):
    if trigger == 'schedule.weekly':
        days = ('понедельникам', 'вторникам', 'средам', 'четвергам', 'пятницам', 'субботам', 'воскресеньям')
        day = schedule.get('weekday')
        frequency = 'по ' + days[day] if isinstance(day, int) and 0 <= day < 7 else 'еженедельно'
    else:
        frequency = 'ежедневно'
    return f"{frequency}, {schedule.get('time', 'время не указано')} ({schedule.get('timezone', 'пояс не указан')})"
